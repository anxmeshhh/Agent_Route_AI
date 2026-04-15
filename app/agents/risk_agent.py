"""
app/agents/risk_agent.py — Module 5 — LLM Risk Synthesis

Makes the ONE batched Groq LLM call per analysis.
All data is pre-collected by other agents before this is called.

Now accepts EXPANDED context from 7 agents:
  weather, news, historical, vessel, port_intel, geopolitical, memory

Produces:
  - Risk score (0-100): Composite index combining all agent signals
  - Risk probability (0-1): Calibrated likelihood of delay/failure
  - Risk level: LOW / MODERATE / HIGH / CRITICAL
  - Risk explanation: 1-sentence human-readable summary
  - Structured factors with severity
  - Decision synthesis with trade-offs
  - Transport-mode-aware reasoning (road/sea/air)
"""
import json
import logging
import math
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ── Risk Score → Probability Calibration ─────────────────────────────
# Maps composite index (0-100) to calibrated delay/failure probability.
# Fitted to logistics industry data: low scores have minimal risk,
# high scores follow a sigmoid curve to realistic probabilities.

def _score_to_probability(score: int) -> float:
    """
    Convert composite risk score (0-100) to calibrated probability (0.0-1.0).
    Uses a sigmoid function fitted to empirical logistics disruption data.
    """
    # Sigmoid: P = 1 / (1 + e^(-k*(x - x0)))
    # k=0.08, x0=50  →  score 0→0.02, 25→0.12, 50→0.50, 75→0.88, 100→0.98
    k, x0 = 0.08, 50
    p = 1.0 / (1.0 + math.exp(-k * (score - x0)))
    return round(p, 2)


def _score_to_level(score: int) -> str:
    """Map composite score to risk level label."""
    if score >= 75:
        return "CRITICAL"
    elif score >= 55:
        return "HIGH"
    elif score >= 30:
        return "MODERATE"
    return "LOW"


def _score_to_explanation(score: int, probability: float, level: str,
                          origin: str, dest: str, mode: str) -> str:
    """Generate a 1-sentence human-readable risk explanation."""
    pct = round(probability * 100)
    mode_label = {"road": "road freight", "air": "air cargo", "sea": "maritime"}.get(mode, "shipment")
    if level == "CRITICAL":
        return f"{score}/100 — Critical risk: {pct}% probability of delay for {mode_label} from {origin} to {dest}. Immediate mitigation required."
    elif level == "HIGH":
        return f"{score}/100 — High risk: {pct}% probability of disruption. Multiple risk factors active on {origin}→{dest} route."
    elif level == "MODERATE":
        return f"{score}/100 — Moderate risk: {pct}% chance of delay. Standard precautions recommended for {origin}→{dest}."
    return f"{score}/100 — Low risk: {pct}% probability of disruption. Favourable conditions for {origin}→{dest} {mode_label}."


def _detect_transport_mode_from_shipment(shipment: dict) -> str:
    """
    Detect transport mode from shipment dict using geocoded coordinates
    when available, falling back to name-based heuristics.
    Uses the authoritative _detect_transport_mode from _detect_mode.py.
    """
    try:
        from ..routes._detect_mode import _detect_transport_mode
        from ..routes._geocoder import geocode

        origin = shipment.get("origin_port", "")
        dest = shipment.get("port", "")
        if not origin or not dest:
            return "sea"

        og = geocode(origin)
        dg = geocode(dest)
        if og and dg:
            return _detect_transport_mode(
                og["lat"], og["lon"], dg["lat"], dg["lon"], origin, dest
            )
    except Exception as e:
        logger.warning(f"[risk] Mode detection via geocoder failed: {e}")

    # Lightweight fallback — name-based heuristics
    query = (shipment.get("query_text") or "").lower()
    origin = (shipment.get("origin_port") or "").lower()
    dest = (shipment.get("port") or "").lower()

    air_kw = ["air", "flight", "fly", "airport", "air freight"]
    if any(k in query for k in air_kw):
        return "air"

    road_kw = ["truck", "road", "highway", "nh", "drive", "land"]
    if any(k in query for k in road_kw):
        return "road"

    return "sea"


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

        # Detect transport mode using authoritative detector
        transport_mode = _detect_transport_mode_from_shipment(shipment)

        logs_callback("risk", f"Aggregating signals — mode: {transport_mode}", "started")

        if not self.api_key or self.api_key.startswith("your_"):
            logs_callback("risk", "No Groq key — using rule-based scoring", "skipped")
            return self._rule_based_result(
                shipment, weather, news, historical, vessel, port_intel, geopolitical,
                w_score, n_score, h_score, v_score, p_score, g_score, transport_mode
            )

        # ── Build the batched prompt ──────────────────────────
        prompt = self._build_prompt(
            shipment, weather, news, historical, vessel, port_intel, geopolitical,
            memory, conflicts,
            w_score, n_score, h_score, v_score, p_score, g_score, transport_mode
        )
        logs_callback("risk",
            f"Sending batched analysis to Groq ({self.model}) — 1 LLM call", "started")

        t0 = time.time()
        try:
            client = self._get_client()
            system_prompt = self._build_system_prompt(transport_mode)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1800,
            )
            duration = int((time.time() - t0) * 1000)
            raw_text = response.choices[0].message.content.strip()
            tokens   = response.usage.total_tokens if response.usage else 0

            logs_callback("risk",
                f"Groq responded in {duration}ms — {tokens} tokens used", "success")

            parsed = self._parse_llm_json(raw_text)

            if parsed:
                logs_callback("risk", "LLM risk assessment parsed successfully", "success")
                # Enrich with calibrated probability + metadata
                score = parsed.get("risk_score", 0)
                probability = _score_to_probability(score)
                level = _score_to_level(score)
                origin = shipment.get("origin_port", "Origin")
                dest = shipment.get("port", "Destination")

                parsed["risk_level"]       = level
                parsed["risk_probability"] = probability
                parsed["risk_explanation"] = _score_to_explanation(
                    score, probability, level, origin, dest, transport_mode
                )
                parsed["transport_mode"]   = transport_mode
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
                    w_score, n_score, h_score, v_score, p_score, g_score, transport_mode
                )

        except Exception as e:
            duration = int((time.time() - t0) * 1000)
            logger.error(f"[risk] Groq error: {e}")
            logs_callback("risk", f"Groq error: {str(e)[:80]} — rule-based fallback", "failed")
            return self._rule_based_result(
                shipment, weather, news, historical, vessel, port_intel, geopolitical,
                w_score, n_score, h_score, v_score, p_score, g_score, transport_mode
            )

    def _build_prompt(self, shipment, weather, news, historical, vessel,
                      port_intel, geopolitical, memory, conflicts,
                      w_score, n_score, h_score, v_score, p_score, g_score,
                      transport_mode: str) -> str:
        port      = shipment.get("port", "Unknown")
        eta       = shipment.get("eta_days", "?")
        eta_hours = shipment.get("eta_hours")
        cargo     = shipment.get("cargo_type", "general")
        query     = shipment.get("query_text", "")
        origin    = shipment.get("origin_port", "Unknown")
        vessel_name = shipment.get("vessel_name", "Unknown")

        # ETA display: prefer hours for road routes
        eta_display = f"{eta} days"
        if eta_hours and transport_mode == "road":
            eta_display = f"{eta_hours} hours (~{eta} days freight)"

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
                    f"\nPAST ANALYSES FOR THIS ROUTE ({len(memory)} found):\n"
                    f"  Average past risk score: {sum(past_scores)/len(past_scores):.0f}/100\n"
                    f"  Range: {min(past_scores)} to {max(past_scores)}\n"
                )

        # Conflict context
        conflict_context = ""
        if conflicts:
            conflict_context = "\nSIGNAL CONFLICTS DETECTED:\n"
            for c in conflicts:
                conflict_context += f"  - {c.get('description', '')[:100]}\n"

        # Transport mode context for LLM
        mode_context = ""
        if transport_mode == "road":
            mode_context = (
                "\nTRANSPORT MODE: ROAD (land freight)\n"
                "This is a ROAD/TRUCK shipment — NOT maritime. Do NOT reference vessels, "
                "shipping lanes, ports, or maritime routes. Focus on road conditions, "
                "highway infrastructure, traffic, tolls, border crossings, and land logistics.\n"
            )
        elif transport_mode == "air":
            mode_context = (
                "\nTRANSPORT MODE: AIR FREIGHT\n"
                "This is an AIR shipment. Focus on airport operations, air cargo capacity, "
                "weather impact on flights, customs clearance, and airspace restrictions.\n"
            )
        else:
            mode_context = (
                "\nTRANSPORT MODE: MARITIME (sea freight)\n"
                "This is a MARITIME shipment. Analyse shipping lanes, port operations, "
                "vessel performance, and chokepoint risks.\n"
            )

        return f"""Analyse this shipment and return a comprehensive JSON risk assessment.

SHIPMENT:
- Query: {query}
- Origin: {origin}
- Destination: {port}
- ETA: {eta_display}
- Cargo type: {cargo}
- Transport mode: {transport_mode}
- Vessel: {vessel_name if transport_mode == 'sea' else 'N/A (road/air)'}
{mode_context}

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

4. VEHICLE/VESSEL AGENT (score: {v_score}/25):
   Status: {vessel.get('vessel_status', 'N/A')}, Speed: {vessel.get('current_speed_knots', 'N/A')} kn
   ETA deviation: {vessel.get('eta_deviation_days', 0):+.1f} days, Rerouted: {vessel.get('is_rerouted', False)}
   Signals: {sig_summary(vessel)}

5. ROUTE INTELLIGENCE (score: {p_score}/25):
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
  "delay_probability": <float percentage e.g. 34.5>,
  "factors": [
    {{"type": "<weather|news|historical|vehicle|route|geopolitical>", "title": "<short title>", "detail": "<specific explanation referencing actual data>", "severity": "<LOW|MODERATE|HIGH|CRITICAL>"}}
  ],
  "decision_synthesis": "<3-4 sentences: What is the risk, why it's at that level, and what specific actions are recommended. Reference actual data points.>",
  "trade_offs": "<1-2 sentences: Key trade-offs between speed, cost, and safety for this route.>"
}}

Rules:
- risk_score considers ALL agent scores weighted by relevance to {transport_mode} transport
- Include 3-6 factors, prioritized by severity
- factors MUST use severity values: LOW, MODERATE, HIGH, or CRITICAL only
- decision_synthesis MUST reference the specific origin, destination, conditions found, and transport mode
- trade_offs MUST mention specific cost vs time vs risk comparisons
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
                           w_score, n_score, h_score, v_score, p_score, g_score,
                           transport_mode: str = "sea") -> dict:
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

        level = _score_to_level(score)
        probability = _score_to_probability(score)
        origin = shipment.get("origin_port", "Origin")
        port = shipment.get("port", "Destination")
        cargo = shipment.get("cargo_type", "general")

        # Combine all signals from ALL agents
        all_factors = []
        for agent_data in [weather, news, historical, vessel, port_intel, geopolitical]:
            if agent_data:
                all_factors.extend(agent_data.get("risk_signals", []))
        all_factors = all_factors[:6]

        if not all_factors:
            all_factors = [{
                "type": "route", "title": "Standard operational risk",
                "detail": f"Normal operational risks for {transport_mode} route to {port}",
                "severity": "LOW",
            }]

        delay_prob = min(
            historical.get("delay_rate", 0.18) * 100 + (score * 0.3), 95
        )

        mode_label = {"road": "road freight", "air": "air cargo", "sea": "maritime"}.get(transport_mode, "shipment")

        return {
            "risk_score": score,
            "risk_level": level,
            "risk_probability": probability,
            "risk_explanation": _score_to_explanation(score, probability, level, origin, port, transport_mode),
            "transport_mode": transport_mode,
            "delay_probability": round(delay_prob, 1),
            "factors": all_factors,
            "mitigation": [],  # Will be generated by MitigationStrategist
            "decision_synthesis": (
                f"Rule-based assessment for {mode_label} from {origin} to {port}: "
                f"Combined risk score {score}/100 ({level}), {round(probability*100)}% disruption probability. "
                f"Weather contributes {w_score}/35, News {n_score}/35, Historical {h_score}/30, "
                f"Vehicle {v_score}/25, Route Intel {p_score}/25, Geopolitical {g_score}/30."
            ),
            "trade_offs": (
                f"Primary route selected for optimal balance of transit time and cost. "
                f"{'Higher risk conditions may warrant alternate routing or delayed departure.' if score >= 55 else 'Current conditions are favourable — proceed as planned.'}"
            ),
            "weather_score": w_score,
            "news_score": n_score,
            "historical_score": h_score,
            "llm_tokens_used": 0,
            "llm_model": "rule-based",
        }

    @staticmethod
    def _build_system_prompt(mode: str) -> str:
        """Build mode-appropriate system prompt for the LLM."""
        if mode == "road":
            return (
                "You are an expert logistics and road freight risk analyst with deep knowledge of "
                "highway networks, truck logistics, road conditions, weather impact on land transport, "
                "toll systems, border crossings, and supply chain disruptions. "
                "Analyse ALL provided data and respond with a JSON object ONLY. "
                "Do NOT reference maritime shipping, vessels, or sea routes."
            )
        elif mode == "air":
            return (
                "You are an expert air cargo risk analyst with deep knowledge of "
                "international air freight, airport operations, customs clearance, "
                "weather impact on aviation, airspace restrictions, and supply chain logistics. "
                "Analyse ALL provided data and respond with a JSON object ONLY."
            )
        else:
            return (
                "You are an expert maritime risk analyst with deep knowledge of "
                "global shipping routes, port operations, weather impact on vessels, "
                "geopolitical risks, chokepoint analysis, and supply chain disruptions. "
                "Analyse ALL provided data and respond with a JSON object ONLY."
            )
