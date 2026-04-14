"""
app/agents/port_intel_agent.py — Port Intelligence Agent

Real-time port intelligence via two complementary data sources:
  1. Structural baseline profiles (capacity, historical efficiency, region)
  2. Live Tavily search for current port news (congestion, strikes, closures)

The PORT_PROFILES dict contains ONLY structural/capacity data — not live status.
All real-time operational status is fetched from Tavily on every call.
"""
import json
import logging
import time
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Structural port profiles — capacity / region / efficiency BASELINES only.
# These never go out of date (TEU capacity, region). Live status via Tavily.
PORT_PROFILES = {
    "jebel ali": {
        "region": "Middle East", "capacity_teu": 19_000_000,
        "avg_wait_hours": 12, "congestion_baseline": "LOW",
        "labor_risk": "LOW", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.92, "peak_months": [10, 11, 12, 1],
    },
    "rotterdam": {
        "region": "Europe", "capacity_teu": 14_800_000,
        "avg_wait_hours": 8, "congestion_baseline": "LOW",
        "labor_risk": "MEDIUM", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.95, "peak_months": [9, 10, 11],
    },
    "shanghai": {
        "region": "East Asia", "capacity_teu": 47_000_000,
        "avg_wait_hours": 24, "congestion_baseline": "MEDIUM",
        "labor_risk": "LOW", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.88, "peak_months": [6, 7, 8, 10, 11],
    },
    "singapore": {
        "region": "Southeast Asia", "capacity_teu": 38_000_000,
        "avg_wait_hours": 6, "congestion_baseline": "LOW",
        "labor_risk": "LOW", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.96, "peak_months": [10, 11, 12],
    },
    "mumbai": {
        "region": "South Asia", "capacity_teu": 5_500_000,
        "avg_wait_hours": 36, "congestion_baseline": "HIGH",
        "labor_risk": "MEDIUM", "infrastructure": "MODERATE",
        "efficiency_index": 0.72, "peak_months": [10, 11, 12, 1, 2],
    },
    "hamburg": {
        "region": "Europe", "capacity_teu": 8_700_000,
        "avg_wait_hours": 10, "congestion_baseline": "LOW",
        "labor_risk": "MEDIUM", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.91, "peak_months": [9, 10, 11],
    },
    "los angeles": {
        "region": "North America", "capacity_teu": 9_200_000,
        "avg_wait_hours": 18, "congestion_baseline": "MEDIUM",
        "labor_risk": "HIGH", "infrastructure": "GOOD",
        "efficiency_index": 0.80, "peak_months": [8, 9, 10, 11],
    },
    "busan": {
        "region": "East Asia", "capacity_teu": 22_000_000,
        "avg_wait_hours": 8, "congestion_baseline": "LOW",
        "labor_risk": "LOW", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.94, "peak_months": [7, 8, 10, 11],
    },
    "antwerp": {
        "region": "Europe", "capacity_teu": 12_000_000,
        "avg_wait_hours": 10, "congestion_baseline": "LOW",
        "labor_risk": "MEDIUM", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.93, "peak_months": [9, 10, 11],
    },
    "colombo": {
        "region": "South Asia", "capacity_teu": 7_200_000,
        "avg_wait_hours": 14, "congestion_baseline": "MEDIUM",
        "labor_risk": "MEDIUM", "infrastructure": "GOOD",
        "efficiency_index": 0.82, "peak_months": [10, 11, 12, 5, 6],
    },
    "nhava sheva": {
        "region": "South Asia", "capacity_teu": 5_800_000,
        "avg_wait_hours": 30, "congestion_baseline": "HIGH",
        "labor_risk": "MEDIUM", "infrastructure": "MODERATE",
        "efficiency_index": 0.74, "peak_months": [10, 11, 12, 1],
    },
    "felixstowe": {
        "region": "Europe", "capacity_teu": 4_000_000,
        "avg_wait_hours": 12, "congestion_baseline": "LOW",
        "labor_risk": "MEDIUM", "infrastructure": "GOOD",
        "efficiency_index": 0.88, "peak_months": [9, 10, 11],
    },
    "barcelona": {
        "region": "Europe", "capacity_teu": 3_500_000,
        "avg_wait_hours": 10, "congestion_baseline": "LOW",
        "labor_risk": "LOW", "infrastructure": "GOOD",
        "efficiency_index": 0.87, "peak_months": [7, 8, 10],
    },
    "hong kong": {
        "region": "East Asia", "capacity_teu": 18_000_000,
        "avg_wait_hours": 18, "congestion_baseline": "MEDIUM",
        "labor_risk": "LOW", "infrastructure": "EXCELLENT",
        "efficiency_index": 0.90, "peak_months": [10, 11, 12],
    },
}

# Live signal keywords — for parsing Tavily article content
_STRIKE_KW    = ["strike", "labor dispute", "walkout", "industrial action", "workers protest", "dock workers"]
_CLOSURE_KW   = ["closed", "closure", "operations suspended", "shut down", "port shut", "blocked entry"]
_CONGESTION_KW = ["congestion", "backlog", "queue", "waiting time", "dwell time", "vessel queue", "port delay"]


class PortIntelAgent:
    """Port operational intelligence — structural baseline + Tavily live news fusion."""

    def __init__(self, db_execute, config: dict):
        self.execute   = db_execute
        self.config    = config
        self.tavily_key = config.get("TAVILY_API_KEY", "")

    def run(self, port: str, port_city: str, session_id: str) -> dict:
        logs = []
        result = {
            "port": port,
            "port_city": port_city,
            "congestion_level": "UNKNOWN",
            "avg_wait_hours": 0,
            "berth_availability": "normal",
            "labor_status": "normal",
            "infrastructure_rating": "MODERATE",
            "efficiency_index": 0.80,
            "port_score": 0,
            "risk_signals": [],
            "live_news_count": 0,
            "logs": logs,
        }

        if not port and not port_city:
            logs.append(self._log("No port specified — skipping port intelligence", "skipped"))
            return result

        search_key = (port or port_city or "").lower()

        # ── 1. Structural baseline ──────────────────────────────────────
        logs.append(self._log(f"Loading structural profile for: {port or port_city}", "started"))
        profile = None
        for key, data in PORT_PROFILES.items():
            if key in search_key or search_key in key or \
               any(word in search_key for word in key.split() if len(word) > 3):
                profile = data
                break

        if not profile:
            logs.append(self._log("Port not in baseline index — using global average profile", "skipped"))
            profile = {
                "region": "Unknown", "capacity_teu": 5_000_000,
                "avg_wait_hours": 18, "congestion_baseline": "MEDIUM",
                "labor_risk": "MEDIUM", "infrastructure": "MODERATE",
                "efficiency_index": 0.80, "peak_months": [10, 11, 12],
            }
        else:
            logs.append(self._log(
                f"✅ Baseline — Region: {profile['region']}, TEU capacity: {profile['capacity_teu']:,}/yr",
                "success"
            ))

        # ── 2. Seasonal adjustment ──────────────────────────────────────
        current_month = datetime.utcnow().month
        is_peak = current_month in profile.get("peak_months", [])
        base_wait = profile["avg_wait_hours"]
        if is_peak:
            adjusted_wait = int(base_wait * 1.4)
            congestion = self._escalate_congestion(profile["congestion_baseline"])
            logs.append(self._log(
                f"⚠ Peak season month {current_month} — wait: {base_wait}h → {adjusted_wait}h",
                "success"
            ))
        else:
            adjusted_wait = base_wait
            congestion = profile["congestion_baseline"]

        result.update({
            "avg_wait_hours":      adjusted_wait,
            "congestion_level":    congestion,
            "labor_status":        profile["labor_risk"],
            "infrastructure_rating": profile["infrastructure"],
            "efficiency_index":    profile["efficiency_index"],
        })

        # ── 3. Live Tavily search for current port status ───────────────
        live_articles = []
        if self.tavily_key and not self.tavily_key.startswith("your_"):
            logs.append(self._log(
                f"🌐 Querying Tavily for live {port or port_city} port status...", "started"
            ))
            t0 = time.time()
            live_articles = self._fetch_live_port_news(port or port_city)
            ms = int((time.time() - t0) * 1000)
            result["live_news_count"] = len(live_articles)
            if live_articles:
                logs.append(self._log(
                    f"Tavily: {len(live_articles)} live articles retrieved in {ms}ms",
                    "success"
                ))
            else:
                logs.append(self._log(
                    f"Tavily: no current port alerts found ({ms}ms)", "skipped"
                ))
        else:
            logs.append(self._log("No Tavily API key — skipping live port news", "skipped"))

        # ── 4. Parse live articles into real-time signals ───────────────
        live_signals, live_delta = self._parse_live_articles(live_articles, port or port_city)

        # Upgrade congestion/labor based on live findings
        for sig in live_signals:
            t_lower = sig["title"].lower()
            if any(k in t_lower for k in ["congestion", "delay", "backlog"]):
                congestion = self._escalate_congestion(congestion)
                result["congestion_level"] = congestion
            if any(k in t_lower for k in ["strike", "labor", "walkout"]):
                result["labor_status"] = "HIGH"

        # ── 5. Historical DB cross-check ────────────────────────────────
        logs.append(self._log("Querying historical port performance from MySQL...", "started"))
        try:
            db_stats = self._query_port_stats(port or port_city)
            if db_stats and db_stats.get("total", 0) > 0:
                db_delay_rate = float(db_stats.get("delay_rate") or 0)
                logs.append(self._log(
                    f"MySQL: {db_stats['total']} records — "
                    f"{db_delay_rate*100:.0f}% historical delay rate",
                    "success"
                ))
                if db_delay_rate > 0.4:
                    congestion = self._escalate_congestion(congestion)
                    result["congestion_level"] = congestion
            else:
                logs.append(self._log("No historical records for this port in MySQL", "skipped"))
        except Exception as e:
            logs.append(self._log(f"DB query error: {e}", "failed"))

        # ── 6. Compose final risk signals ───────────────────────────────
        signals = list(live_signals)  # live signals first (highest priority)
        score = live_delta

        if congestion == "HIGH":
            signals.append({
                "type": "port", "severity": "HIGH",
                "title": f"High port congestion: {port or port_city}",
                "detail": f"Wait time: ~{adjusted_wait}h. Efficiency: {profile['efficiency_index']:.0%}.",
                "confidence": 0.8,
            })
            score += 12
        elif congestion == "MEDIUM":
            signals.append({
                "type": "port", "severity": "MEDIUM",
                "title": "Moderate congestion expected",
                "detail": f"Wait time: ~{adjusted_wait}h. Port within normal capacity.",
                "confidence": 0.7,
            })
            score += 6

        if result["labor_status"] == "HIGH":
            signals.append({
                "type": "port", "severity": "HIGH",
                "title": "Elevated labor dispute risk",
                "detail": "Active or imminent labor action signals detected.",
                "confidence": 0.75,
            })
            score += 8
        elif profile["labor_risk"] == "MEDIUM":
            signals.append({
                "type": "port", "severity": "LOW",
                "title": "Moderate labor relations risk",
                "detail": "Periodic negotiations possible — no confirmed active disputes.",
                "confidence": 0.5,
            })
            score += 3

        if is_peak:
            signals.append({
                "type": "port", "severity": "MEDIUM",
                "title": "Peak shipping season",
                "detail": f"Month {current_month} is historically high-volume at {port or port_city}.",
                "confidence": 0.8,
            })
            score += 5

        result["risk_signals"] = signals[:6]
        result["port_score"]   = min(score, 25)

        logs.append(self._log(
            f"✅ Port intel complete — score: {result['port_score']}/25, "
            f"congestion: {congestion}, live articles: {len(live_articles)}, "
            f"signals: {len(signals)}",
            "success",
            {"score": result["port_score"], "congestion": congestion, "live": len(live_articles)},
        ))
        result["logs"] = logs
        return result

    # ─── Tavily live news fetch ──────────────────────────────────────
    def _fetch_live_port_news(self, port: str) -> list:
        """Search Tavily for real-time port congestion / strike / closure news."""
        query = f'"{port}" port operations congestion delay strike closure 2025'
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": 5,
                    "days": 30,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            logger.warning(f"[port_intel] Tavily error: {e}")
            return []

    def _parse_live_articles(self, articles: list, port: str) -> tuple:
        """Parse Tavily results into port risk signals. Returns (signals, score_delta)."""
        signals, score = [], 0
        port_words = set((port or "").lower().split())

        for art in articles[:5]:
            title   = art.get("title", "")
            content = art.get("content", "")
            url     = art.get("url", "")
            text    = f"{title} {content}".lower()

            # Require port name to appear in the text
            if port_words and not any(w in text for w in port_words if len(w) > 3):
                continue

            if any(k in text for k in _STRIKE_KW):
                signals.append({
                    "type": "port", "severity": "HIGH",
                    "title": f"🔴 LIVE — Labor action at {port}",
                    "detail": title[:150],
                    "url": url, "confidence": 0.88, "source": "Tavily",
                })
                score += 8
            elif any(k in text for k in _CLOSURE_KW):
                signals.append({
                    "type": "port", "severity": "HIGH",
                    "title": f"🔴 LIVE — Operations disrupted at {port}",
                    "detail": title[:150],
                    "url": url, "confidence": 0.85, "source": "Tavily",
                })
                score += 10
            elif any(k in text for k in _CONGESTION_KW):
                signals.append({
                    "type": "port", "severity": "MEDIUM",
                    "title": f"🟡 LIVE — Congestion reported at {port}",
                    "detail": title[:150],
                    "url": url, "confidence": 0.80, "source": "Tavily",
                })
                score += 5

        return signals[:3], min(score, 15)

    def _query_port_stats(self, port: str) -> Optional[dict]:
        rows = self.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) / COUNT(*) AS delay_rate,
                      AVG(CASE WHEN delay_days > 0 THEN delay_days ELSE NULL END) AS avg_delay
               FROM historical_shipments WHERE LOWER(port) LIKE LOWER(%s)""",
            (f"%{port}%",), fetch=True,
        )
        return rows[0] if rows else None

    def _escalate_congestion(self, level: str) -> str:
        return {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "HIGH"}.get(level, "MEDIUM")

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "port_intel", "action": action, "status": status, "data": data}
