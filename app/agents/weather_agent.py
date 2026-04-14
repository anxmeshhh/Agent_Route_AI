"""
app/agents/weather_agent.py — Module 2

Fetches real weather data from OpenWeatherMap for a port city.
Caches results in MySQL (TTL: 1 hour) to save API calls.
No LLM involved — pure data collection and risk signal extraction.

Agentic behaviour:
  - Checks cache first (TTL-aware)
  - Fetches from API only on cache miss
  - Returns structured risk signals with severity scoring
  - Gracefully degrades if API key missing or call fails
"""
import json
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# OpenWeather API endpoint
OW_BASE = "https://api.openweathermap.org/data/2.5"

# Risk thresholds for weather signals
WIND_RISK = [
    (20, "HIGH",   "Severe wind speed — port operations likely disrupted"),
    (14, "MEDIUM", "Strong winds — vessel manoeuvring may be impacted"),
    (8,  "LOW",    "Moderate winds — minor operational delays possible"),
]
VISIBILITY_RISK = [
    (2000,  "HIGH",   "Very low visibility — navigation risk"),
    (5000,  "MEDIUM", "Reduced visibility — caution advised"),
]
STORM_CONDITIONS = [
    "Thunderstorm", "Storm", "Tornado", "Hurricane", "Squall",
    "Blizzard", "Extreme", "Hail",
]


class WeatherAgent:
    """
    Module 2: Fetches and interprets port weather data.
    """

    def __init__(self, db_execute, config: dict):
        self.execute = db_execute
        self.api_key = config.get("OPENWEATHER_API_KEY", "")
        self.ttl     = int(config.get("WEATHER_CACHE_TTL", 3600))  # seconds

    def run(self, port_city: str, session_id: str) -> dict:
        """
        Returns a weather risk dict:
        {
            "source": "cache" | "api" | "fallback",
            "port_city": str,
            "conditions": str,
            "wind_speed": float,   # m/s
            "temperature": float,  # Celsius
            "visibility": int,     # metres
            "risk_signals": [...],
            "weather_score": int,  # 0–35
            "logs": [...]
        }
        """
        logs = []
        result = {
            "port_city": port_city,
            "source": "fallback",
            "conditions": "Unknown",
            "wind_speed": 0,
            "temperature": None,
            "visibility": 10000,
            "risk_signals": [],
            "weather_score": 0,
            "logs": logs,
        }

        if not port_city:
            logs.append(self._log("No port city provided — skipping weather fetch", "skipped"))
            return result

        # ── Check cache ────────────────────────────────────────────
        logs.append(self._log(f"Checking weather cache for {port_city}...", "started"))
        cached = self._check_cache(port_city)

        if cached:
            logs.append(self._log(f"✅ Cache hit — using stored weather (expires soon: no)", "success"))
            data = cached
            result["source"] = "cache"
        elif not self.api_key or self.api_key == "your_openweather_api_key_here":
            # No API key — use realistic fallback based on port region
            logs.append(self._log("No OpenWeather API key — using regional estimate", "skipped"))
            data = self._regional_fallback(port_city)
            result["source"] = "fallback"
        else:
            # ── Fetch from API ─────────────────────────────────────
            logs.append(self._log(f"Cache miss — fetching live weather for {port_city}", "started"))
            t0 = time.time()
            try:
                data = self._fetch_weather(port_city)
                duration = int((time.time() - t0) * 1000)
                logs.append(self._log(f"OpenWeather API responded in {duration}ms", "success"))
                self._save_cache(port_city, data)
                logs.append(self._log("Weather data cached in MySQL (TTL: 1hr)", "success"))
                result["source"] = "api"
            except Exception as e:
                logger.warning(f"[weather] API error for {port_city}: {e}")
                logs.append(self._log(f"API error: {e} — using fallback", "failed"))
                data = self._regional_fallback(port_city)
                result["source"] = "fallback"

        # ── Populate result ────────────────────────────────────────
        result["conditions"]   = data.get("conditions", "Clear")
        result["wind_speed"]   = data.get("wind_speed", 0)
        result["temperature"]  = data.get("temperature")
        result["visibility"]   = data.get("visibility", 10000)

        # ── Score & extract risk signals ───────────────────────────
        signals, score = self._score_weather(data)
        result["risk_signals"] = signals
        result["weather_score"] = score

        logs.append(self._log(
            f"Weather risk scored: {score}/35 — {len(signals)} signal(s) detected",
            "success",
            {"score": score, "signals": len(signals)},
        ))

        result["logs"] = logs
        return result

    # ─── API fetch ─────────────────────────────────────────────────
    def _fetch_weather(self, city: str) -> dict:
        # Step 1: Geocoding via Nominatim (OpenStreetMap)
        geo_resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "ShipRiskAI/1.0"},
            timeout=8,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        
        if not geo_data:
            raise ValueError(f"Could not resolve coordinates for city: {city}")
            
        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]
        
        # Step 2: Weather via OpenWeatherMap
        weather_resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric"
            },
            timeout=8,
        )
        weather_resp.raise_for_status()
        raw = weather_resp.json()
        
        weather_array = raw.get("weather", [])
        if weather_array:
            cond = weather_array[0].get("main", "Clear")
            desc = weather_array[0].get("description", "")
        else:
            cond = "Variable"
            desc = "Unknown"
            
        main_data = raw.get("main", {})
        wind_data = raw.get("wind", {})
            
        return {
            "conditions":  cond,
            "description": desc,
            "wind_speed":  wind_data.get("speed", 0),  # OWM returns m/s for metric
            "temperature": main_data.get("temp", 0),
            "visibility":  raw.get("visibility", 10000),
            "raw":         raw,
        }

    # ─── Cache ────────────────────────────────────────────────────
    def _check_cache(self, city: str) -> Optional[dict]:
        try:
            rows = self.execute(
                """SELECT data_json FROM weather_cache
                   WHERE port_city = %s AND expires_at > NOW()
                   ORDER BY fetched_at DESC LIMIT 1""",
                (city,), fetch=True,
            )
            if rows and rows[0]["data_json"]:
                return json.loads(rows[0]["data_json"]) if isinstance(rows[0]["data_json"], str) else rows[0]["data_json"]
        except Exception as e:
            logger.warning(f"[weather] Cache read error: {e}")
        return None

    def _save_cache(self, city: str, data: dict):
        try:
            expires = datetime.utcnow() + timedelta(seconds=self.ttl)
            self.execute(
                """INSERT INTO weather_cache
                       (port_city, data_json, wind_speed, conditions, temperature, visibility, fetched_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                   ON DUPLICATE KEY UPDATE
                       data_json=VALUES(data_json), wind_speed=VALUES(wind_speed),
                       conditions=VALUES(conditions), temperature=VALUES(temperature),
                       visibility=VALUES(visibility), fetched_at=NOW(), expires_at=VALUES(expires_at)""",
                (city, json.dumps(data), data.get("wind_speed", 0),
                 data.get("conditions", ""), data.get("temperature"), data.get("visibility"),
                 expires),
            )
        except Exception as e:
            logger.warning(f"[weather] Cache write error: {e}")

    # ─── Risk scoring ──────────────────────────────────────────────
    def _score_weather(self, data: dict) -> tuple[list, int]:
        signals = []
        score = 0
        wind  = data.get("wind_speed", 0)
        cond  = data.get("conditions", "")
        vis   = data.get("visibility", 10000)

        # Storm / severe condition (major factor — up to 20pts)
        if any(s.lower() in cond.lower() for s in STORM_CONDITIONS):
            signals.append({
                "type": "weather", "title": f"Severe weather: {cond}",
                "detail": "Active storm system detected near port — operations likely suspended",
                "severity": "HIGH",
            })
            score += 20

        # Wind speed (up to 12 pts)
        for threshold, severity, msg in WIND_RISK:
            if wind >= threshold:
                signals.append({
                    "type": "weather",
                    "title": f"Wind speed: {wind:.1f} m/s ({wind*3.6:.0f} km/h)",
                    "detail": msg, "severity": severity,
                })
                pts = {"HIGH": 12, "MEDIUM": 7, "LOW": 3}[severity]
                score += pts
                break

        # Visibility (up to 8 pts)
        for threshold, severity, msg in VISIBILITY_RISK:
            if vis <= threshold:
                signals.append({
                    "type": "weather",
                    "title": f"Low visibility: {vis}m",
                    "detail": msg, "severity": severity,
                })
                score += {"HIGH": 8, "MEDIUM": 4}[severity]
                break

        return signals, min(score, 35)

    def _regional_fallback(self, city: str) -> dict:
        """Returns a realistic estimate when API unavailable. Covers India cities too."""
        city_lower = city.lower()
        # Middle East
        if any(x in city_lower for x in ["dubai", "jebel", "abu dhabi", "doha", "muscat"]):
            wind, cond, temp = 4.5, "Clear", 34
        # Northern Europe
        elif any(x in city_lower for x in ["rotterdam", "hamburg", "antwerp", "felixstowe"]):
            wind, cond, temp = 7.2, "Cloudy", 12
        # East China / Korea
        elif any(x in city_lower for x in ["shanghai", "ningbo", "tianjin", "busan"]):
            wind, cond, temp = 5.8, "Haze", 22
        # Southeast Asia
        elif any(x in city_lower for x in ["singapore", "colombo", "klang", "tanjung"]):
            wind, cond, temp = 3.1, "Partly Cloudy", 29
        # India — North (dry, summer heat)
        elif any(x in city_lower for x in ["delhi", "new delhi", "jaipur", "agra", "lucknow", "kanpur"]):
            wind, cond, temp = 3.5, "Haze", 38
        # India — West (Mumbai, Gujarat)
        elif any(x in city_lower for x in ["mumbai", "pune", "ahmedabad", "surat", "rajkot"]):
            wind, cond, temp = 4.2, "Partly Cloudy", 32
        # India — South (Kerala, TN, Karnataka)
        elif any(x in city_lower for x in ["kerala", "thiruvananthapuram", "trivandrum",
                                            "kochi", "cochin", "bangalore", "bengaluru",
                                            "chennai", "madurai", "coimbatore"]):
            wind, cond, temp = 4.8, "Partly Cloudy", 30
        # India — Hyderabad / AP
        elif any(x in city_lower for x in ["hyderabad", "visakhapatnam", "vijayawada"]):
            wind, cond, temp = 3.9, "Clear", 36
        # India — East (Kolkata, Odisha)
        elif any(x in city_lower for x in ["kolkata", "bhubaneswar", "patna"]):
            wind, cond, temp = 4.0, "Partly Cloudy", 34
        # Americas
        elif any(x in city_lower for x in ["los angeles", "long beach", "new york", "houston"]):
            wind, cond, temp = 4.0, "Clear", 22
        # Default
        else:
            wind, cond, temp = 5.0, "Clear", 25

        return {
            "conditions": cond, "wind_speed": wind,
            "temperature": temp, "visibility": 9000,
        }

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "weather", "action": action, "status": status, "data": data}

