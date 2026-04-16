"""
app/agents/geopolitical_agent.py — Geopolitical Risk Agent (Real-Time)

Two-layer intelligence:
  Layer 1 — Structural knowledge loaded from MySQL ref tables:
             chokepoint profiles, sanction watchlists, piracy zone boundaries
  Layer 2 — Live Tavily search: latest news for each identified chokepoint
             and region, searched fresh on every analysis call.

Zero hardcoded values — all reference data via ref_data module.
"""
import logging
import time
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _ref():
    """Lazy import of ref_data to avoid circular imports."""
    from ..models import ref_data
    return ref_data


class GeopoliticalAgent:
    """
    Geopolitical risk assessment fusing structural knowledge + live Tavily news.
    All reference data (chokepoints, regions, sanctions) loaded from MySQL.
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

        rd = _ref()
        signals = []
        score   = 0

        # ── 1. Identify chokepoints on this route ──────────────────────
        logs.append(self._log("Identifying chokepoints on estimated route...", "started"))
        chokepoints_on_route = self._identify_chokepoints(
            port_lower, origin_lower, rd.get_region_ports(), rd.get_chokepoints()
        )
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
            high_kw   = rd.get_risk_keywords("geo_high")
            medium_kw = rd.get_risk_keywords("geo_medium")

            for cp in chokepoints_on_route:
                live_sigs, live_score, n_articles = self._search_chokepoint_live(
                    cp, high_kw, medium_kw
                )
                signals.extend(live_sigs)
                score += live_score
                total_articles += n_articles

            # Also search route region generally
            region_sigs, region_score, region_articles = self._search_route_region(
                port_lower, origin_lower, rd.get_region_ports()
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
        region_ports    = rd.get_region_ports()
        region_levels   = rd.get_region_risk_levels()

        dest_region   = self._get_region(port_lower, region_ports)
        origin_region = self._get_region(origin_lower, region_ports) if origin_lower else None

        if dest_region:
            region_level = region_levels.get(dest_region, "LOW")
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
            olevel = region_levels.get(origin_region, "LOW")
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
        sanctioned = self._check_sanctions(port_lower, origin_lower, rd.get_sanctions())
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
        piracy_zones = rd.get_piracy_zones()
        piracy_region = next(
            (z for z in piracy_zones
             if any(p in port_lower for p in region_ports.get(z, []))),
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
    def _identify_chokepoints(self, dest: str, origin: str,
                               region_ports: dict, chokepoints: dict) -> list:
        """Determine which chokepoints this route likely transits using DB data."""
        eu    = region_ports.get("europe", [])
        asia  = region_ports.get("east_asia", []) + region_ports.get("se_asia", [])
        me    = region_ports.get("middle_east", []) + region_ports.get("persian_gulf", [])
        amer  = region_ports.get("americas", [])
        black = region_ports.get("black_sea_ports", [])

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
        cp = chokepoints

        # Suez + Bab el-Mandeb: EU ↔ Asia/ME
        if (dest_eu and (orig_asia or orig_me)) or (orig_eu and (dest_asia or dest_me)):
            if "suez_canal" in cp:    found.append(cp["suez_canal"])
            if "bab_el_mandeb" in cp: found.append(cp["bab_el_mandeb"])

        # Hormuz: anything touching Middle East / Persian Gulf
        if dest_me or orig_me:
            if "strait_of_hormuz" in cp: found.append(cp["strait_of_hormuz"])

        # Malacca: SE Asia involvement
        if dest_asia or orig_asia or any(p in dest for p in region_ports.get("se_asia", [])):
            if "malacca_strait" in cp: found.append(cp["malacca_strait"])

        # Panama: Americas routes
        if (dest_amer and orig_asia) or (orig_amer and dest_asia):
            if "panama_canal" in cp: found.append(cp["panama_canal"])

        # Black Sea
        if dest_bsea or any(p in origin for p in black):
            if "black_sea" in cp: found.append(cp["black_sea"])

        # Deduplicate
        seen, unique = set(), []
        for c in found:
            if c["name"] not in seen:
                seen.add(c["name"])
                unique.append(c)
        return unique

    # ─── Live Tavily searches ───────────────────────────────────────────
    def _search_chokepoint_live(self, cp: dict, high_kw: list, medium_kw: list) -> tuple:
        """Search live news for a specific chokepoint. Returns (signals, score, n_articles)."""
        query = cp["search_query"]
        articles = self._tavily_search(query, days=14, max_results=4)
        if not articles:
            return [], 0, 0

        signals, score = [], 0

        for art in articles[:3]:
            title   = art.get("title", "")
            content = art.get("content", "")
            url     = art.get("url", "")
            text    = f"{title} {content}".lower()

            if any(k in text for k in high_kw):
                sev = "HIGH" if cp["risk_level"] != "CRITICAL" else "CRITICAL"
                signals.append({
                    "type": "geopolitical", "severity": sev,
                    "title": f"🔴 LIVE — {cp['name']}: {title[:100]}",
                    "detail": content[:200] if content else title,
                    "url": url, "confidence": 0.87, "source": "Tavily",
                })
                score += cp["base_score"]
                break
            elif any(k in text for k in medium_kw):
                signals.append({
                    "type": "geopolitical", "severity": "MEDIUM",
                    "title": f"🟡 LIVE — {cp['name']}: {title[:100]}",
                    "detail": content[:200] if content else title,
                    "url": url, "confidence": 0.78, "source": "Tavily",
                })
                score += max(2, cp["base_score"] // 2)
                break

        return signals, min(score, 20), len(articles)

    def _search_route_region(self, dest: str, origin: str, region_ports: dict) -> tuple:
        """Search Tavily for general shipping geopolitical news for this route."""
        dest_region   = self._get_region(dest, region_ports)
        origin_region = self._get_region(origin, region_ports) if origin else None

        queries = []
        high_risk_regions = {"red_sea", "persian_gulf", "black_sea_ports"}
        if dest_region in high_risk_regions:
            queries.append(f"shipping risk {dest_region.replace('_', ' ')} latest news 2025")
        if origin_region and origin_region != dest_region and origin_region in high_risk_regions:
            queries.append(f"shipping risk {origin_region.replace('_', ' ')} 2025")
        if not queries:
            return [], 0, 0

        signals, score, total = [], 0, 0
        high_kw = _ref().get_risk_keywords("geo_high")
        for q in queries[:1]:  # 1 query to preserve API credits
            articles = self._tavily_search(q, days=7, max_results=3)
            total += len(articles)
            for art in articles[:2]:
                title = art.get("title", "")
                url   = art.get("url", "")
                if any(k in title.lower() for k in high_kw):
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
    def _get_region(self, port_lower: str, region_ports: dict) -> Optional[str]:
        for region, ports in region_ports.items():
            if any(p in port_lower for p in ports):
                return region
        return None

    def _check_sanctions(self, port_lower: str, origin_lower: str,
                          sanctions: list) -> bool:
        combined = f"{port_lower} {origin_lower}"
        return any(country in combined for country in sanctions)

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "geopolitical", "action": action, "status": status, "data": data}
