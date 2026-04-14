"""
app/agents/geopolitical_agent.py — Geopolitical Risk Agent (Real-Time)

Two-layer intelligence:
  Layer 1 — Structural knowledge: chokepoint physics, sanction watchlists,
             piracy zone boundaries (these don't change hour-to-hour)
  Layer 2 — Live Tavily search: latest news for each identified chokepoint
             and region, searched fresh on every analysis call.

The agent fuses both layers into a final geo_score (0-30) + signals.
"""
import logging
import time
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Structural chokepoint knowledge (geography / physics — rarely changes) ──────
CHOKEPOINTS = {
    "suez_canal": {
        "name": "Suez Canal",
        "search_query": "Suez Canal shipping disruption closure delay 2025",
        "base_score": 6, "risk_level": "MEDIUM",
        "routes_eu_asia": True, "routes_eu_me": True,
    },
    "bab_el_mandeb": {
        "name": "Bab el-Mandeb / Red Sea",
        "search_query": "Red Sea shipping attack Houthi Bab el-Mandeb 2025",
        "base_score": 14, "risk_level": "HIGH",
        "routes_eu_asia": True, "routes_eu_me": True,
    },
    "strait_of_hormuz": {
        "name": "Strait of Hormuz",
        "search_query": "Strait of Hormuz Iran tanker shipping risk 2025",
        "base_score": 10, "risk_level": "HIGH",
        "routes_me_any": True,
    },
    "malacca_strait": {
        "name": "Strait of Malacca",
        "search_query": "Strait of Malacca piracy congestion shipping 2025",
        "base_score": 3, "risk_level": "LOW",
        "routes_se_asia": True,
    },
    "panama_canal": {
        "name": "Panama Canal",
        "search_query": "Panama Canal drought water level delay restrictions 2025",
        "base_score": 5, "risk_level": "MEDIUM",
        "routes_americas": True,
    },
    "black_sea": {
        "name": "Black Sea",
        "search_query": "Black Sea shipping Ukraine Russia war mine risk 2025",
        "base_score": 16, "risk_level": "CRITICAL",
        "routes_black_sea": True,
    },
}

# Port-to-region mapping (structural — geography doesn't change)
REGION_PORTS = {
    "red_sea":        ["aden", "djibouti", "salalah", "jeddah", "port sudan", "hudaydah"],
    "persian_gulf":   ["jebel ali", "dubai", "doha", "abu dhabi", "bahrain", "kuwait", "muscat"],
    "south_china_sea":["ho chi minh", "manila", "singapore", "haiphong"],
    "gulf_guinea":    ["lagos", "tema", "abidjan", "lome", "douala", "dakar"],
    "east_africa":    ["mombasa", "dar es salaam", "mogadishu", "maputo"],
    "black_sea_ports":["odessa", "constanta", "novorossiysk", "batumi"],
    "europe":         ["rotterdam", "hamburg", "antwerp", "felixstowe", "barcelona", "genoa", "piraeus", "le havre"],
    "east_asia":      ["shanghai", "ningbo", "shenzhen", "busan", "hong kong", "tianjin", "qingdao"],
    "se_asia":        ["singapore", "klang", "tanjung pelepas", "colombo", "jakarta"],
    "south_asia":     ["mumbai", "nhava sheva", "chennai", "kolkata", "karachi", "chittagong"],
    "americas":       ["los angeles", "long beach", "new york", "panama", "houston", "santos", "callao"],
    "middle_east":    ["jebel ali", "dubai", "doha", "abu dhabi", "salalah", "aden"],
}

# Known sanctions-risk jurisdictions (OFAC / EU / UN — updated periodically)
SANCTIONS_COUNTRIES = [
    "north korea", "korea (north)", "dprk",
    "iran", "iranian",
    "syria", "syrian",
    "cuba", "cuban",
    "crimea",
    "russia", "russian",
    "belarus", "belarusian",
    "myanmar", "burma",
    "venezuela",
    "sudan",
    "zimbabwe",
]

# Piracy risk zones (IMB data)
PIRACY_ZONES = ["gulf_guinea", "east_africa", "red_sea"]


class GeopoliticalAgent:
    """
    Geopolitical risk assessment fusing structural knowledge + live Tavily news.
    """

    def __init__(self, db_execute, config: dict):
        self.execute    = db_execute
        self.config     = config
        self.tavily_key = config.get("TAVILY_API_KEY", "")

    def run(self, port: str, origin_port: str, route_region: str,
            session_id: str) -> dict:
        logs = []
        result = {
            "port": port,
            "origin_port": origin_port,
            "chokepoints": [],
            "region_risk": "LOW",
            "sanctions_risk": False,
            "piracy_risk": "LOW",
            "geo_score": 0,
            "risk_signals": [],
            "live_articles_searched": 0,
            "logs": logs,
        }

        if not port:
            logs.append(self._log("No destination port — skipping geopolitical analysis", "skipped"))
            return result

        port_lower   = port.lower()
        origin_lower = (origin_port or "").lower()

        logs.append(self._log(
            f"🌍 Geopolitical assessment: {origin_port or '?'} → {port}", "started"
        ))

        signals = []
        score   = 0

        # ── 1. Identify chokepoints on this route ──────────────────────
        logs.append(self._log("Identifying chokepoints on estimated route...", "started"))
        chokepoints_on_route = self._identify_chokepoints(port_lower, origin_lower)
        result["chokepoints"] = [c["name"] for c in chokepoints_on_route]

        if chokepoints_on_route:
            logs.append(self._log(
                f"Chokepoints identified: {', '.join(result['chokepoints'])}", "success"
            ))
        else:
            logs.append(self._log("No critical chokepoints on this route", "success"))

        # ── 2. Live Tavily search for each identified chokepoint ────────
        if self.tavily_key and not self.tavily_key.startswith("your_"):
            logs.append(self._log(
                f"🌐 Searching live news for {len(chokepoints_on_route)} chokepoint(s) + route region...",
                "started"
            ))
            total_articles = 0
            for cp in chokepoints_on_route:
                live_sigs, live_score, n_articles = self._search_chokepoint_live(cp)
                signals.extend(live_sigs)
                score += live_score
                total_articles += n_articles

            # Also search route region generally
            region_sigs, region_score, region_articles = self._search_route_region(
                port_lower, origin_lower
            )
            signals.extend(region_sigs)
            score += region_score
            total_articles += region_articles

            result["live_articles_searched"] = total_articles
            logs.append(self._log(
                f"Tavily: {total_articles} live geopolitical articles searched",
                "success" if total_articles > 0 else "skipped"
            ))
        else:
            logs.append(self._log("No Tavily key — using structural risk profiles only", "skipped"))
            # Fall back to structural base scores
            for cp in chokepoints_on_route:
                if cp["risk_level"] in ("HIGH", "MEDIUM", "CRITICAL"):
                    signals.append({
                        "type": "geopolitical", "severity": cp["risk_level"],
                        "title": f"Route transits {cp['name']}",
                        "detail": f"Structural risk: {cp['risk_level']} chokepoint on route.",
                        "confidence": 0.75,
                    })
                    score += cp["base_score"]

        # ── 3. Regional risk assessment ─────────────────────────────────
        logs.append(self._log("Assessing destination and origin regions...", "started"))
        dest_region   = self._get_region(port_lower)
        origin_region = self._get_region(origin_lower) if origin_lower else None

        if dest_region:
            region_level = self._region_risk_level(dest_region)
            result["region_risk"] = region_level
            if region_level in ("HIGH", "CRITICAL"):
                signals.append({
                    "type": "geopolitical", "severity": region_level,
                    "title": f"Destination in {dest_region.replace('_', ' ').title()} risk zone",
                    "detail": f"Region classified {region_level} based on current intelligence.",
                    "confidence": 0.82,
                })
                score += {"HIGH": 10, "CRITICAL": 16, "MEDIUM": 5, "LOW": 0}.get(region_level, 0)

        if origin_region and origin_region != dest_region:
            olevel = self._region_risk_level(origin_region)
            if olevel in ("HIGH", "CRITICAL"):
                signals.append({
                    "type": "geopolitical", "severity": olevel,
                    "title": f"Origin in {origin_region.replace('_', ' ').title()} risk zone",
                    "detail": f"Origin region: {olevel} risk.",
                    "confidence": 0.75,
                })
                score += {"HIGH": 6, "CRITICAL": 10, "MEDIUM": 3, "LOW": 0}.get(olevel, 0)

        # ── 4. Sanctions screening ───────────────────────────────────────
        logs.append(self._log("Running sanctions & embargo screening...", "started"))
        sanctioned = self._check_sanctions(port_lower, origin_lower)
        result["sanctions_risk"] = sanctioned
        if sanctioned:
            signals.append({
                "type": "geopolitical", "severity": "CRITICAL",
                "title": "⚠ Sanctions / Embargo Risk Detected",
                "detail": ("One or more ports/jurisdictions on this route appear on OFAC/EU/UN "
                           "sanctions watchlists. Immediate compliance review required."),
                "confidence": 0.96,
            })
            score += 28
            logs.append(self._log("⚠ Sanctions flag raised — compliance review required", "success"))
        else:
            logs.append(self._log("No sanctions flags detected on this route", "success"))

        # ── 5. Piracy risk assessment ────────────────────────────────────
        piracy_region = next(
            (z for z in PIRACY_ZONES
             if any(p in port_lower for p in REGION_PORTS.get(z, []))),
            None
        )
        if piracy_region:
            result["piracy_risk"] = "HIGH" if piracy_region in ["gulf_guinea", "red_sea"] else "MEDIUM"
            signals.append({
                "type": "geopolitical", "severity": "HIGH",
                "title": f"Piracy risk zone: {piracy_region.replace('_', ' ').title()}",
                "detail": "IMB-designated high-incident zone. Armed escort / convoy routing recommended.",
                "confidence": 0.82,
            })
            score += 10

        result["risk_signals"] = signals[:8]
        result["geo_score"]    = min(score, 30)

        logs.append(self._log(
            f"✅ Geopolitical complete — score: {result['geo_score']}/30, "
            f"chokepoints: {len(chokepoints_on_route)}, "
            f"live articles: {result['live_articles_searched']}, "
            f"signals: {len(signals)}",
            "success",
            {"score": result["geo_score"], "chokepoints": result["chokepoints"]}
        ))
        result["logs"] = logs
        return result

    # ─── Chokepoint identification ──────────────────────────────────────
    def _identify_chokepoints(self, dest: str, origin: str) -> list:
        """Determine which chokepoints this route likely transits."""
        eu    = [p for p in REGION_PORTS["europe"]]
        asia  = [p for p in REGION_PORTS["east_asia"] + REGION_PORTS["se_asia"]]
        me    = [p for p in REGION_PORTS["middle_east"] + REGION_PORTS["persian_gulf"]]
        amer  = [p for p in REGION_PORTS["americas"]]
        black = [p for p in REGION_PORTS["black_sea_ports"]]

        dest_eu   = any(p in dest for p in eu)
        dest_asia = any(p in dest for p in asia)
        dest_me   = any(p in dest for p in me)
        dest_amer = any(p in dest for p in amer)
        dest_bsea = any(p in dest for p in black)

        orig_eu   = any(p in origin for p in eu)
        orig_asia = any(p in origin for p in asia)
        orig_me   = any(p in origin for p in me)
        orig_amer = any(p in origin for p in amer)

        found = []

        # Suez: EU ↔ Asia/ME
        if (dest_eu and (orig_asia or orig_me)) or (orig_eu and (dest_asia or dest_me)):
            found.append(CHOKEPOINTS["suez_canal"])

        # Bab el-Mandeb: same routes as Suez (before/after)
        if (dest_eu and (orig_asia or orig_me)) or (orig_eu and (dest_asia or dest_me)):
            found.append(CHOKEPOINTS["bab_el_mandeb"])

        # Hormuz: anything touching Middle East / Persian Gulf
        if dest_me or orig_me:
            found.append(CHOKEPOINTS["strait_of_hormuz"])

        # Malacca: SE Asia involvement
        if dest_asia or orig_asia or any(p in dest for p in REGION_PORTS["se_asia"]):
            found.append(CHOKEPOINTS["malacca_strait"])

        # Panama: Americas routes
        if (dest_amer and orig_asia) or (orig_amer and dest_asia):
            found.append(CHOKEPOINTS["panama_canal"])

        # Black Sea
        if dest_bsea or any(p in origin for p in black):
            found.append(CHOKEPOINTS["black_sea"])

        # Deduplicate
        seen, unique = set(), []
        for cp in found:
            if cp["name"] not in seen:
                seen.add(cp["name"])
                unique.append(cp)
        return unique

    # ─── Live Tavily searches ───────────────────────────────────────────
    def _search_chokepoint_live(self, cp: dict) -> tuple:
        """Search live news for a specific chokepoint. Returns (signals, score, n_articles)."""
        query = cp["search_query"]
        articles = self._tavily_search(query, days=14, max_results=4)
        if not articles:
            return [], 0, 0

        signals, score = [], 0
        HIGH_KW   = ["attack", "missile", "closure", "blocked", "war", "seized", "military",
                     "explosion", "fire", "sanctions", "embargo", "conflict"]
        MEDIUM_KW = ["disruption", "delay", "restricted", "incident", "tension", "protest",
                     "drought", "congestion", "queue", "restriction"]

        for art in articles[:3]:
            title   = art.get("title", "")
            content = art.get("content", "")
            url     = art.get("url", "")
            text    = f"{title} {content}".lower()

            if any(k in text for k in HIGH_KW):
                sev = "HIGH" if cp["risk_level"] != "CRITICAL" else "CRITICAL"
                signals.append({
                    "type": "geopolitical", "severity": sev,
                    "title": f"🔴 LIVE — {cp['name']}: {title[:100]}",
                    "detail": content[:200] if content else title,
                    "url": url, "confidence": 0.87, "source": "Tavily",
                })
                score += cp["base_score"]
                break
            elif any(k in text for k in MEDIUM_KW):
                signals.append({
                    "type": "geopolitical", "severity": "MEDIUM",
                    "title": f"🟡 LIVE — {cp['name']}: {title[:100]}",
                    "detail": content[:200] if content else title,
                    "url": url, "confidence": 0.78, "source": "Tavily",
                })
                score += max(2, cp["base_score"] // 2)
                break

        return signals, min(score, 20), len(articles)

    def _search_route_region(self, dest: str, origin: str) -> tuple:
        """Search Tavily for general shipping geopolitical news for this route."""
        # Build a targeted query based on the regions involved
        dest_region   = self._get_region(dest)
        origin_region = self._get_region(origin) if origin else None

        queries = []
        if dest_region in ("red_sea", "persian_gulf", "black_sea_ports"):
            queries.append(f"shipping risk {dest_region.replace('_', ' ')} latest news 2025")
        if origin_region and origin_region != dest_region:
            if origin_region in ("red_sea", "persian_gulf", "black_sea_ports"):
                queries.append(f"shipping risk {origin_region.replace('_', ' ')} 2025")
        if not queries:
            return [], 0, 0

        signals, score, total = [], 0, 0
        for q in queries[:1]:  # 1 query to preserve API credits
            articles = self._tavily_search(q, days=7, max_results=3)
            total += len(articles)
            for art in articles[:2]:
                title = art.get("title", "")
                url   = art.get("url", "")
                if any(k in title.lower() for k in ["attack", "war", "closure", "blocked"]):
                    signals.append({
                        "type": "geopolitical", "severity": "HIGH",
                        "title": f"🔴 LIVE — Route region alert: {title[:120]}",
                        "detail": art.get("content", "")[:200],
                        "url": url, "confidence": 0.80, "source": "Tavily",
                    })
                    score += 8

        return signals[:2], min(score, 12), total

    def _tavily_search(self, query: str, days: int = 14, max_results: int = 4) -> list:
        """Generic Tavily search wrapper."""
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
                    "max_results": max_results,
                    "days": days,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            logger.warning(f"[geo] Tavily error ({query[:40]}...): {e}")
            return []

    # ─── Region / sanctions helpers ─────────────────────────────────────
    def _get_region(self, port_lower: str) -> Optional[str]:
        for region, ports in REGION_PORTS.items():
            if any(p in port_lower for p in ports):
                return region
        return None

    def _region_risk_level(self, region: str) -> str:
        mapping = {
            "red_sea": "HIGH", "persian_gulf": "MEDIUM",
            "south_china_sea": "MEDIUM", "gulf_guinea": "HIGH",
            "east_africa": "MEDIUM", "black_sea_ports": "CRITICAL",
            "europe": "LOW", "east_asia": "LOW",
            "se_asia": "LOW", "south_asia": "LOW",
            "americas": "LOW", "middle_east": "MEDIUM",
        }
        return mapping.get(region, "LOW")

    def _check_sanctions(self, port_lower: str, origin_lower: str) -> bool:
        combined = f"{port_lower} {origin_lower}"
        return any(country in combined for country in SANCTIONS_COUNTRIES)

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "geopolitical", "action": action, "status": status, "data": data}
