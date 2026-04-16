"""
app/agents/precaution_agent.py — Threat Detection & Smart Rerouting Agent

Features:
  1. Induce Threat  — generates a random realistic maritime threat mid-route
  2. Reroute        — generates multiple alternative routes (air / sea / land)
                      with cost estimates, weather context, and risk scoring
                      using ONLY Groq API (llama-3.1-8b-instant)
"""

import os, json, logging, random
from typing import Optional
from groq import Groq

logger     = logging.getLogger(__name__)
GROQ_MODEL = "llama-3.1-8b-instant"

# ── Prompts ───────────────────────────────────────────────────────────────────

_THREAT_SYS = """You are a maritime risk intelligence system. Generate ONE realistic
mid-route threat event that could affect a shipment. Be specific and vivid.

Return ONLY raw JSON (no markdown, no explanation):
{
  "threat_id": "<6-char alphanumeric>",
  "type": "<piracy|storm|port_closure|mechanical|geopolitical|fire|collision|strike|earthquake|flood>",
  "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "title": "<short punchy title>",
  "description": "<2-3 sentences describing the specific threat, location, and immediate impact>",
  "location": "<specific location where threat occurred>",
  "estimated_delay_days": <integer 1-30>,
  "affected_radius_km": <integer>,
  "recommended_action": "<immediate action to take>",
  "threat_color": "<#hexcode matching severity: LOW=#f59e0b, MEDIUM=#ef4444, HIGH=#dc2626, CRITICAL=#7f1d1d>"
}"""

_REROUTE_SYS = """You are an expert global logistics router. Given a threat situation,
generate exactly 4 alternative routes from source to destination.

Include a MIX of modes: at least 1 air freight, 2 sea (different paths), 1 multimodal.
Each route must be realistic, specific, and detailed with actual port/city names.

Return ONLY raw JSON array (no markdown):
[
  {
    "route_id": "<R1|R2|R3|R4>",
    "mode": "<AIR|SEA|MULTIMODAL>",
    "type": "<piracy|storm|port_closure|mechanical|geopolitical|fire|collision|strike|earthquake|flood — same as the active threat type>",
    "label": "<short distinctive name, e.g. 'Northern Sea Bypass'>",
    "waypoints": ["<city/port 1>", "<city/port 2>", "...up to 5 waypoints>"],
    "transit_days": <integer>,
    "original_transit_days": <integer>,
    "cost_usd": <integer, realistic freight cost>,
    "original_cost_usd": <integer>,
    "cost_change_pct": <float, positive=more expensive>,
    "risk_level": "<LOW|MEDIUM|HIGH>",
    "risk_score": <integer 0-100>,
    "risk_reason": "<1-sentence explanation of why this route has this risk score, e.g. 'Avoids threat zone + stable weather conditions'>",
    "weather_outlook": "<brief current weather situation along this route>",
    "pros": ["<pro 1>", "<pro 2>", "<pro 3>"],
    "cons": ["<con 1>", "<con 2>"],
    "carrier_examples": ["<carrier name>", "<carrier name>"],
    "recommended": <true for the single best option, false for others>,
    "recommendation_reason": "<why this is or isn't the top pick>"
  }
]"""

_WEATHER_SYS = """You are a maritime meteorologist. Given source and destination ports,
describe current weather conditions along major shipping lanes between them.

Return ONLY raw JSON (no markdown):
{
  "overall_outlook": "<CLEAR|MODERATE|ROUGH|SEVERE>",
  "summary": "<2 sentences overall>",
  "zones": [
    {
      "zone": "<sea/region name>",
      "condition": "<CLEAR|MODERATE|ROUGH|SEVERE>",
      "detail": "<specific weather detail>"
    }
  ],
  "advisory": "<any active weather advisories>"
}"""


class PrecautionAgent:

    def __init__(self, config: dict):
        groq_key   = config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
        self._groq = Groq(api_key=groq_key) if groq_key else None
        self._threat_cache: dict = {}   # session_id → last threat
        self._route_cache:  dict = {}   # session_id → last routes

    # ─── Public API ───────────────────────────────────────────────────────────

    def induce_threat(self, source: str, destination: str,
                      cargo_type: str, session_id: str) -> dict:
        """Generate a random realistic threat mid-route."""
        if not self._groq:
            return self._error("Groq API key not configured")

        threat_types = [
            "piracy", "storm", "port_closure", "mechanical",
            "geopolitical", "fire", "collision", "strike", "earthquake", "flood"
        ]
        chosen = random.choice(threat_types)

        try:
            resp = self._groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _THREAT_SYS},
                    {"role": "user", "content": (
                        f"Generate a {chosen} threat for a shipment travelling "
                        f"from {source} to {destination} carrying {cargo_type} cargo. "
                        f"Make it specific to this route and cargo type."
                    )},
                ],
                max_tokens=500, temperature=0.85,
            )
            raw    = self._clean(resp.choices[0].message.content or "")
            threat = json.loads(raw)

            # Normalise: ensure both 'type' and 'threat_type' are present and consistent
            _ttype = threat.get("type") or threat.get("threat_type", "unknown")
            threat["type"]        = _ttype
            threat["threat_type"] = _ttype

            # Enrich with route context
            threat["source"]      = source
            threat["destination"] = destination
            threat["cargo_type"]  = cargo_type
            threat["session_id"]  = session_id

            # Cache for rerouting
            self._threat_cache[session_id] = threat
            logger.info(f"[precaution] Threat induced: {_ttype} "
                        f"severity={threat.get('severity')}")
            return {"success": True, "threat": threat}

        except Exception as e:
            logger.error(f"[precaution] Threat induction failed: {e}")
            return self._error(str(e))

    def get_reroutes(self, source: str, destination: str,
                     cargo_type: str, session_id: str,
                     threat: Optional[dict] = None) -> dict:
        """Generate multiple alternative routes given a threat."""
        if not self._groq:
            return self._error("Groq API key not configured")

        # Use cached threat if not provided
        if not threat:
            threat = self._threat_cache.get(session_id, {})

        threat_desc = ""
        if threat:
            threat_desc = (
                f"ACTIVE THREAT: {threat.get('threat_type','unknown').upper()} — "
                f"{threat.get('title','')}. {threat.get('description','')} "
                f"Location: {threat.get('location','')}. "
                f"Severity: {threat.get('severity','MEDIUM')}."
            )

        # Fetch weather context first
        weather = self._get_weather(source, destination)

        weather_ctx = ""
        if weather:
            weather_ctx = (
                f"WEATHER: {weather.get('overall_outlook','')} conditions. "
                f"{weather.get('summary','')} Advisory: {weather.get('advisory','none')}."
            )

        try:
            resp = self._groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _REROUTE_SYS},
                    {"role": "user", "content": (
                        f"Source: {source}\n"
                        f"Destination: {destination}\n"
                        f"Cargo: {cargo_type}\n"
                        f"{threat_desc}\n"
                        f"{weather_ctx}\n\n"
                        f"Generate 4 alternative routes avoiding the threat zone. "
                        f"Include real port names and realistic costs."
                    )},
                ],
                max_tokens=2000, temperature=0.4,
            )
            raw    = self._clean(resp.choices[0].message.content or "")
            routes = json.loads(raw)

            # Ensure it's a list
            if isinstance(routes, dict):
                routes = [routes]

            # Normalise type field on each route to match threat type, and
            # apply severity-aware recommendation logic
            severity   = (threat.get("severity") or "MEDIUM").upper()
            threat_type = threat.get("type") or threat.get("threat_type", "unknown")
            high_severity = severity in ("HIGH", "CRITICAL")

            for r in routes:
                r["source"]      = source
                r["destination"] = destination
                # Keep threat type consistent on every route
                r["type"] = threat_type
                # Ensure risk_reason exists
                if not r.get("risk_reason"):
                    r["risk_reason"] = (
                        f"Risk score {r.get('risk_score', '?')}/100 — "
                        f"{r.get('weather_outlook', 'weather data unavailable')}"
                    )

            # ── Severity-aware recommendation override ────────────────────────
            # For HIGH/CRITICAL threats speed matters most → prefer AIR route.
            # For LOW/MEDIUM threats keep cost-balanced recommendation from LLM.
            if high_severity:
                air_routes = [r for r in routes if r.get("mode") == "AIR"]
                if air_routes:
                    # Pick fastest air route
                    best_air = min(air_routes, key=lambda r: r.get("transit_days", 999))
                    for r in routes:
                        if r["route_id"] == best_air["route_id"]:
                            r["recommended"] = True
                            r["recommendation_reason"] = (
                                f"Severity is {severity}: speed takes priority over cost. "
                                f"Air freight is the fastest option at {best_air.get('transit_days')} days, "
                                f"minimising exposure and delivery risk."
                            )
                        else:
                            r["recommended"] = False

            # ── Build final_recommendation block ──────────────────────────────
            recommended = next((r for r in routes if r.get("recommended")), None)
            if not recommended and routes:
                # Fallback: lowest risk_score
                recommended = min(routes, key=lambda r: r.get("risk_score", 100))
                recommended["recommended"] = True

            final_recommendation = None
            if recommended:
                final_recommendation = {
                    "route_id": recommended.get("route_id"),
                    "label":    recommended.get("label"),
                    "mode":     recommended.get("mode"),
                    "reason":   recommended.get("recommendation_reason") or (
                        f"Best balance of cost, time, and risk under current "
                        f"{threat_type} conditions "
                        f"(risk score {recommended.get('risk_score')}/100, "
                        f"{recommended.get('transit_days')} days, "
                        f"${recommended.get('cost_usd'):,} USD)"
                    ),
                }

            self._route_cache[session_id] = routes
            logger.info(f"[precaution] Generated {len(routes)} reroutes for {source}→{destination}")

            return {
                "success":              True,
                "routes":               routes,
                "weather":              weather,
                "threat":               threat,
                "count":                len(routes),
                "final_recommendation": final_recommendation,
            }

        except Exception as e:
            logger.error(f"[precaution] Reroute generation failed: {e}")
            return self._error(str(e))

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _get_weather(self, source: str, destination: str) -> Optional[dict]:
        try:
            resp = self._groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _WEATHER_SYS},
                    {"role": "user", "content": (
                        f"Weather conditions on shipping lanes from {source} to {destination}."
                    )},
                ],
                max_tokens=400, temperature=0.2,
            )
            raw = self._clean(resp.choices[0].message.content or "")
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"[precaution] Weather fetch failed: {e}")
            return None

    def _clean(self, text: str) -> str:
        """Strip markdown code fences from Groq response."""
        text = text.strip()
        for fence in ["```json", "```"]:
            text = text.lstrip(fence)
        text = text.rstrip("```").strip()
        return text

    def _error(self, msg: str) -> dict:
        return {"success": False, "error": msg}