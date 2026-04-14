"""
app/agents/risk_agent.py — Module 5 — LLM Risk Synthesis

Makes the ONE batched Groq LLM call per analysis.
All data is pre-collected by other agents before this is called.

Now accepts EXPANDED context from 7 agents:
  weather, news, historical, vessel, port_intel, geopolitical, memory

The LLM reasons about ALL signals together and produces:
  - Risk score (0-100)
  - Risk level (LOW/MEDIUM/HIGH/CRITICAL)
  - Delay probability
  - Risk factors with severity
  - Narrative reasoning referencing actual data found
"""
import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RiskAgent:
    """Groq LLM synthesis of all agent signals into final risk assessment."""

    def __init__(self, config: dict):
        self.api_key = config.get("GROQ_API_KEY", "")
        self.model = config.get("GROQ_MODEL", "llama3-8b-8192")
        self._client = None

    def _get_client(self):
        if not self._client:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def run(self, context: dict, logs_callback) -> dict:
        """
        Synthesize all agent data into a final risk assessment.
        Uses ONE Groq LLM call with all context batched.
        """
        shipment   = context.get("shipment", {})
        weather    = context.get("weather") or {}
        news       = context.get("news") or {}
        historical = context.get("historical") or {}
        vessel     = context.get("vessel") or {}
        port_intel = context.get("port_intel") or {}
        geopolitical = context.get("geopolitical") or {}
        memory     = context.get("memory_recalls") or []
        conflicts  = context.get("conflicts") or []

        # Pre-calculate sub-scores
        w_score = weather.get("weather_score", 0)
        n_score = news.get("news_score", 0)
        h_score = historical.get("historical_score", 0)
        v_score = vessel.get("vessel_score", 0)
        p_score = port_intel.get("port_score", 0)
        g_score = geopolitical.get("geo_score", 0)

        logs_callback("risk", "Aggregating signals from all agents", "started")

        if not self.api_key or self.api_key.startswith("your_"):
            logs_callback("risk", "No Groq key — using rule-based scoring", "skipped")
            return self._rule_based_result(
                shipment, weather, news, historical, vessel, port_intel, geopolitical,
                w_score, n_score, h_score, v_score, p_score, g_score
            )

        # ── Build the batched prompt ──────────────────────────
        prompt = self._build_prompt(
            shipment, weather, news, historical, vessel, port_intel, geopolitical,
            memory, conflicts,
            w_score, n_score, h_score, v_score, p_score, g_score
        )
        logs_callback("risk",
            f"Sending batched analysis to Groq ({self.model}) — 1 LLM call", "started")

        t0 = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert maritime risk analyst with deep knowledge of "
                            "global shipping routes, port operations, weather impact on vessels, "
                            "geopolitical risks, and supply chain disruptions. "
                            "Analyse ALL provided data and respond with a JSON object ONLY."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            duration = int((time.time() - t0) * 1000)
            raw_text = response.choices[0].message.content.strip()
            tokens   = response.usage.total_tokens if response.usage else 0

            logs_callback("risk",
                f"Groq responded in {duration}ms — {tokens} tokens used", "success")

            parsed = self._parse_llm_json(raw_text)

            if parsed:
                logs_callback("risk", "LLM risk assessment parsed successfully", "success")
                parsed["weather_score"]    = w_score
                parsed["news_score"]       = n_score
                parsed["historical_score"] = h_score
                parsed["llm_tokens_used"]  = tokens
                parsed["llm_model"]        = self.model
                return parsed
            else:
                logs_callback("risk", "LLM response parse failed — using rule-based", "failed")
                return self._rule_based_result(
                    shipment, weather, news, historical, vessel, port_intel, geopolitical,
                    w_score, n_score, h_score, v_score, p_score, g_score
                )

        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            logger.error(f"[risk] Groq error: {e}")
            logs_callback("risk", f"Groq error: {str(e)[:80]} — rule-based fallback", "failed")
            return self._rule_based_result(
                shipment, weather, news, historical, vessel, port_intel, geopolitical,
                w_score, n_score, h_score, v_score, p_score, g_score
            )

    def _build_prompt(self, shipment, weather, news, historical, vessel,
                      port_intel, geopolitical, memory, conflicts,
                      w_score, n_score, h_score, v_score, p_score, g_score) -> str:
        port      = shipment.get("port", "Unknown")
        eta       = shipment.get("eta_days", "?")
        cargo     = shipment.get("cargo_type", "general")
        query     = shipment.get("query_text", "")
        origin    = shipment.get("origin_port", "Unknown")
        vessel_name = shipment.get("vessel_name", "Unknown")

        # Summarize signals from each agent
        def sig_summary(data, key="risk_signals", limit=3):
            sigs = (data or {}).get(key, [])
            if not sigs:
                return "No signals detected"
            return "; ".join(s.get("title", "")[:80] for s in sigs[:limit])

        # Memory context
        memory_context = ""
        if memory:
            past_scores = [m.get("risk_score") for m in memory if m.get("risk_score")]
            if past_scores:
                memory_context = (
                    f"\nPAST ANALYSES FOR THIS PORT ({len(memory)} found):\n"
                    f"  Average past risk score: {sum(past_scores)/len(past_scores):.0f}/100\n"
                    f"  Range: {min(past_scores)} to {max(past_scores)}\n"
                )

        # Conflict context
        conflict_context = ""
        if conflicts:
            conflict_context = "\nSIGNAL CONFLICTS DETECTED:\n"
            for c in conflicts:
                conflict_context += f"  - {c.get('description', '')[:100]}\n"

        return f"""Analyse this shipment and return a comprehensive JSON risk assessment.

SHIPMENT:
- Query: {query}
- Origin: {origin}
- Destination port: {port}
- ETA: {eta} days
- Cargo type: {cargo}
- Vessel: {vessel_name}

DATA FROM 7 SPECIALIZED AGENTS:

1. WEATHER AGENT (score: {w_score}/35):
   Conditions: {weather.get('conditions', 'N/A')}, Wind: {weather.get('wind_speed', 0):.1f}m/s, Temp: {weather.get('temperature', 'N/A')}°C
   Signals: {sig_summary(weather)}
   Source: {weather.get('source', 'N/A')}

2. NEWS AGENT (score: {n_score}/35):
   Source: {news.get('source', 'N/A')}, Articles analysed: {len(news.get('articles', []))}
   Signals: {sig_summary(news)}

3. HISTORICAL AGENT (score: {h_score}/30):
   Records analysed: {historical.get('records_analysed', 0)}, Delay rate: {historical.get('delay_rate', 0)*100:.0f}%
   Avg delay: {historical.get('avg_delay_days', 0):.1f} days, Seasonal: {historical.get('seasonal_risk', 'N/A')}
   Signals: {sig_summary(historical)}

4. VESSEL AGENT (score: {v_score}/25):
   Status: {vessel.get('vessel_status', 'N/A')}, Speed: {vessel.get('current_speed_knots', 'N/A')} kn
   ETA deviation: {vessel.get('eta_deviation_days', 0):+.1f} days, Rerouted: {vessel.get('is_rerouted', False)}
   Signals: {sig_summary(vessel)}

5. PORT INTELLIGENCE (score: {p_score}/25):
   Congestion: {port_intel.get('congestion_level', 'N/A')}, Wait: {port_intel.get('avg_wait_hours', 'N/A')}h
   Labor: {port_intel.get('labor_status', 'N/A')}, Efficiency: {port_intel.get('efficiency_index', 'N/A')}
   Signals: {sig_summary(port_intel)}

6. GEOPOLITICAL AGENT (score: {g_score}/30):
   Region risk: {geopolitical.get('region_risk', 'N/A')}, Sanctions: {geopolitical.get('sanctions_risk', False)}
   Chokepoints: {', '.join(geopolitical.get('chokepoints', [])) or 'None'}
   Piracy: {geopolitical.get('piracy_risk', 'N/A')}
   Signals: {sig_summary(geopolitical)}
{memory_context}{conflict_context}
Return ONLY this JSON (no markdown, no extra text):
{{
  "risk_score": <integer 0-100>,
  "risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "delay_probability": <float percentage e.g. 34.5>,
  "factors": [
    {{"type": "<weather|news|historical|vessel|port|geopolitical>", "title": "<short title>", "detail": "<specific explanation referencing actual data>", "severity": "<LOW|MEDIUM|HIGH|CRITICAL>"}}
  ],
  "mitigation": [
    {{"title": "<strategy title>", "detail": "<actionable detail specific to this shipment>"}}
  ],
  "llm_reasoning": "<3-4 sentence narrative summary referencing specific ports, data points, and agent findings>"
}}

Rules:
- risk_score considers ALL 7 agent scores weighted by relevance
- Include 3-6 factors, prioritized by severity
- Include 3-5 mitigation strategies that are SPECIFIC (mention the port, cargo, actual conditions)
- llm_reasoning MUST reference the specific port name, conditions found, and data points
- If past analyses exist, mention how current risk compares
- If conflicts exist between agents, explain your resolution
"""

    def _parse_llm_json(self, text: str) -> Optional[dict]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning(f"[risk] Could not parse JSON from: {text[:200]}")
        return None

    def _rule_based_result(self, shipment, weather, news, historical,
                           vessel, port_intel, geopolitical,
                           w_score, n_score, h_score, v_score, p_score, g_score) -> dict:
        """Deterministic result when Groq is unavailable."""
        # Weighted combination of all scores
        raw_score = (
            w_score * 0.20 +
            n_score * 0.20 +
            h_score * 0.20 +
            v_score * 0.15 +
            p_score * 0.15 +
            g_score * 0.10
        )
        # Normalize to 0-100
        max_possible = 35*0.20 + 35*0.20 + 30*0.20 + 25*0.15 + 25*0.15 + 30*0.10
        score = min(int((raw_score / max_possible) * 100), 100) if max_possible > 0 else 0

        if score >= 75: level = "CRITICAL"
        elif score >= 55: level = "HIGH"
        elif score >= 30: level = "MEDIUM"
        else: level = "LOW"

        port  = shipment.get("port", "the destination port")
        cargo = shipment.get("cargo_type", "general")

        # Combine all signals from ALL agents
        all_factors = []
        for agent_data in [weather, news, historical, vessel, port_intel, geopolitical]:
            if agent_data:
                all_factors.extend(agent_data.get("risk_signals", []))
        all_factors = all_factors[:6]

        if not all_factors:
            all_factors = [{
                "type": "port", "title": "Standard shipping risk",
                "detail": f"Normal operational risks for {port}",
                "severity": "LOW",
            }]

        delay_prob = min(
            historical.get("delay_rate", 0.18) * 100 + (score * 0.3), 95
        )

        return {
            "risk_score": score,
            "risk_level": level,
            "delay_probability": round(delay_prob, 1),
            "factors": all_factors,
            "mitigation": [],  # Will be generated by MitigationStrategist
            "llm_reasoning": (
                f"Rule-based assessment for shipment to {port}: "
                f"Combined risk score {score}/100 ({level}). "
                f"Weather: {w_score}/35, News: {n_score}/35, Historical: {h_score}/30, "
                f"Vessel: {v_score}/25, Port: {p_score}/25, Geopolitical: {g_score}/30. "
                f"Delay probability: {delay_prob:.0f}%."
            ),
            "weather_score": w_score,
            "news_score": n_score,
            "historical_score": h_score,
            "llm_tokens_used": 0,
            "llm_model": "rule-based",
        }
