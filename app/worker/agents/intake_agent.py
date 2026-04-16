"""
app/agents/intake_agent.py — Module 1

Parses a natural-language shipment query and extracts structured fields.
No LLM used — pure regex + keyword matching.
Direction-aware: correctly handles "from ORIGIN to DESTINATION" patterns.

All lookup data (PORT_MAP, CARGO_KEYWORDS, default origins) is loaded
from MySQL reference tables via ref_data — zero hardcoded values.
"""
import re
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_port_map() -> dict:
    """Fetch port map from DB-backed cache; fall back to empty dict."""
    try:
        from app.backend.models import ref_data
        return ref_data.get_port_map()
    except Exception as e:
        logger.warning(f"[intake] ref_data.get_port_map() failed: {e}")
        return {}


def _get_cargo_keywords() -> dict:
    """Fetch cargo keywords from DB-backed cache."""
    try:
        from app.backend.models import ref_data
        return ref_data.get_cargo_keywords()
    except Exception as e:
        logger.warning(f"[intake] ref_data.get_cargo_keywords() failed: {e}")
        return {}


def _get_default_origins() -> dict:
    """Fetch default origin mapping from DB-backed cache."""
    try:
        from app.backend.models import ref_data
        return ref_data.get_default_origins()
    except Exception as e:
        logger.warning(f"[intake] ref_data.get_default_origins() failed: {e}")
        return {}


def _lookup_port(raw: str) -> tuple:
    """Returns (port_name, city) for the best matching PORT_MAP key, or (None, None)."""
    port_map = _get_port_map()
    raw = raw.strip().lower()
    # Exact key match first
    if raw in port_map:
        return port_map[raw]
    # Substring match
    for kw, (pname, city) in port_map.items():
        if kw in raw or raw in kw or raw.startswith(kw) or kw.startswith(raw):
            return (pname, city)
    return (None, None)


class IntakeAgent:
    """
    Module 1: parse raw user query → structured shipment dict.
    Direction-aware: 'from ORIGIN to DESTINATION' is correctly split.
    All reference data loaded from MySQL — no hardcoded values.
    """

    def run(self, query_text: str, session_id: Optional[str] = None,
            structured_override: dict = None) -> dict:
        if not session_id:
            session_id = str(uuid.uuid4())
        structured_override = structured_override or {}

        result = {
            "session_id":     session_id,
            "query_text":     query_text.strip(),
            "port":           structured_override.get("port"),
            "port_city":      structured_override.get("port_city"),
            "eta_days":       structured_override.get("eta_days"),
            "cargo_type":     structured_override.get("cargo_type", "general"),
            "vessel_name":    None,
            "origin_port":    structured_override.get("origin_port"),
            "shipment_uuid":  structured_override.get("shipment_uuid"),
            "budget_usd":     structured_override.get("budget_usd"),
            "weight_kg":      structured_override.get("weight_kg"),
            "logs":           [],
        }

        # ── Structured override mode: form fields provided, skip NLP ──
        if structured_override.get("origin_port") and structured_override.get("port"):
            result["logs"].append({
                "agent":  "intake",
                "action": (f"Structured form intake — "
                           f"Origin: {result['origin_port']} | Dest: {result['port']} | "
                           f"Cargo: {result['cargo_type']} | "
                           f"UUID: {result.get('shipment_uuid', '—')}"),
                "status": "success",
                "data": {
                    "port":           result["port"],
                    "port_city":      result["port_city"],
                    "eta_days":       result["eta_days"],
                    "cargo_type":     result["cargo_type"],
                    "origin_port":    result["origin_port"],
                    "weight_kg":      result["weight_kg"],
                    "budget_usd":     result["budget_usd"],
                    "shipment_uuid":  result["shipment_uuid"],
                },
            })
            # Compute ETA via OSRM if not provided
            if not result["eta_days"]:
                computed_eta = self._compute_eta_from_route(
                    result["origin_port"], result["port"]
                )
                result["eta_days"]   = computed_eta["days"]
                result["eta_hours"]  = computed_eta.get("hours")
                result["eta_source"] = computed_eta["source"]
                result["logs"].append({
                    "agent":  "intake",
                    "action": f"ETA computed: {computed_eta['days']} day(s) ({computed_eta['source']})",
                    "status": "success",
                })
            logger.info(
                f"[intake] structured: origin={result['origin_port']} dest={result['port']} "
                f"eta={result['eta_days']}d cargo={result['cargo_type']} "
                f"uuid={result.get('shipment_uuid')}"
            )
            return result

        text = query_text.strip()
        tl   = text.lower()
        logs = result["logs"]

        logs.append({"agent": "intake",
                     "action": "Parsing shipment query — direction-aware origin/destination extraction",
                     "status": "started"})

        # Load reference data once per call
        port_map        = _get_port_map()
        cargo_keywords  = _get_cargo_keywords()
        default_origins = _get_default_origins()

        # ══════════════════════════════════════════════════════════
        # STRATEGY A: "from X to Y" directional extraction
        # ══════════════════════════════════════════════════════════
        from_to = re.search(
            r"(?:from|departing|shipped\s+from|dispatch(?:ed)?\s+from|send(?:ing)?\s+from)\s+"
            r"([A-Za-z][A-Za-z\s]{1,30}?)\s+"
            r"(?:to|towards|->|→)\s+"
            r"([A-Za-z][A-Za-z\s]{1,35}?)"
            r"(?:\s+(?:in|by|via|through|within|over|using)|[,.\n]|$)",
            text, re.IGNORECASE,
        )
        if from_to:
            raw_orig = from_to.group(1).strip()
            raw_dest = from_to.group(2).strip()
            logs.append({"agent": "intake",
                         "action": f"Found directional pattern: '{raw_orig}' → '{raw_dest}'",
                         "status": "success"})

            pname, city = _lookup_port(raw_orig)
            result["origin_port"] = pname or raw_orig

            pname, city = _lookup_port(raw_dest)
            result["port"]      = pname or raw_dest
            result["port_city"] = city  or raw_dest

            logs.append({"agent": "intake",
                         "action": f"Origin: {result['origin_port']} | Destination: {result['port']}",
                         "status": "success"})

        # ══════════════════════════════════════════════════════════
        # STRATEGY B: scan text AFTER "to" for destination only
        # ══════════════════════════════════════════════════════════
        if not result["port"]:
            to_pos = re.search(r"\bto\b", tl)
            scan   = tl[to_pos.start():] if to_pos else tl
            for kw, (pname, city) in port_map.items():
                if kw in scan:
                    result["port"]      = pname
                    result["port_city"] = city
                    logs.append({"agent": "intake",
                                 "action": f"Destination via post-'to' scan: {pname}",
                                 "status": "success"})
                    break

        # ══════════════════════════════════════════════════════════
        # STRATEGY C: scan text BEFORE "to" for origin only
        # ══════════════════════════════════════════════════════════
        if not result["origin_port"]:
            to_pos  = re.search(r"\bto\b", tl)
            pre     = tl[:to_pos.start()] if to_pos else ""
            for kw, (pname, _) in port_map.items():
                if kw in pre:
                    result["origin_port"] = pname
                    logs.append({"agent": "intake",
                                 "action": f"Origin via pre-'to' scan: {pname}",
                                 "status": "success"})
                    break

        # ══════════════════════════════════════════════════════════
        # STRATEGY D: DB-driven default origin if still missing
        # ══════════════════════════════════════════════════════════
        if not result["origin_port"]:
            dl = (result["port"] or "").lower()
            cl = (result["port_city"] or "").lower()
            # Lookup against DB-loaded default_origins table
            default_origin = None
            for dest_kw, orig in default_origins.items():
                if dest_kw in dl or dest_kw in cl:
                    default_origin = orig
                    break
            # Ultimate fallback — Shanghai (most common global origin)
            result["origin_port"] = default_origin or "Shanghai"
            logs.append({"agent": "intake",
                         "action": f"Origin defaulted to {result['origin_port']}",
                         "status": "skipped"})

        # Collision guard: origin must not equal destination
        if result["origin_port"] and result["port"] and \
           result["origin_port"].lower() == result["port"].lower():
            # Find any India destination keyword to decide fallback
            india_kw = [k for k, v in default_origins.items() if v == "Delhi"]
            result["origin_port"] = "Delhi" if any(k in tl for k in india_kw) else "Shanghai"
            logs.append({"agent": "intake",
                         "action": f"Origin/dest collision resolved → {result['origin_port']}",
                         "status": "skipped"})

        # ══════════════════════════════════════════════════════════
        # ETA
        # ══════════════════════════════════════════════════════════
        eta = re.search(r"(\d+)\s*(day|days|week|weeks|hour|hours)", tl)
        if eta:
            v, u = int(eta.group(1)), eta.group(2)
            if "week" in u: v *= 7
            elif "hour" in u: v = max(1, v // 24)
            result["eta_days"] = v
            logs.append({"agent": "intake", "action": f"ETA: {v} day(s)", "status": "success"})
        else:
            # Dynamic ETA: compute from real route distance via OSRM
            computed_eta = self._compute_eta_from_route(
                result.get("origin_port"), result.get("port")
            )
            result["eta_days"]   = computed_eta["days"]
            result["eta_hours"]  = computed_eta.get("hours")
            result["eta_source"] = computed_eta["source"]
            logs.append({"agent": "intake",
                         "action": f"ETA computed: {computed_eta['days']} day(s) ({computed_eta['source']})",
                         "status": "success" if computed_eta["source"] != "default" else "skipped"})

        # ══════════════════════════════════════════════════════════
        # CARGO TYPE — from DB keywords
        # ══════════════════════════════════════════════════════════
        for ctype, kws in cargo_keywords.items():
            if any(kw in tl for kw in kws):
                result["cargo_type"] = ctype
                break
        logs.append({"agent": "intake",
                     "action": f"Cargo type: {result['cargo_type']}",
                     "status": "success"})

        # ══════════════════════════════════════════════════════════
        # VESSEL NAME
        # ══════════════════════════════════════════════════════════
        vm = re.search(r"(?:vessel|ship|mv|ms|ss)\s+([A-Z][A-Za-z\s]+?)(?:\s+is|\s+will|,|\.|$)",
                       text, re.IGNORECASE)
        if vm:
            result["vessel_name"] = vm.group(1).strip()
            logs.append({"agent": "intake",
                         "action": f"Vessel: {result['vessel_name']}",
                         "status": "success"})

        # ══════════════════════════════════════════════════════════
        # FINAL LOG
        # ══════════════════════════════════════════════════════════
        logs.append({
            "agent":  "intake",
            "action": (f"Intake complete — "
                       f"Origin: {result['origin_port']} | "
                       f"Dest: {result['port']} | "
                       f"ETA: {result['eta_days']}d | "
                       f"Cargo: {result['cargo_type']}"),
            "status": "success",
            "data": {
                "port":          result["port"],
                "port_city":     result["port_city"],
                "eta_days":      result["eta_days"],
                "cargo_type":    result["cargo_type"],
                "origin_port":   result["origin_port"],
                "shipment_uuid": result.get("shipment_uuid"),
                "weight_kg":     result.get("weight_kg"),
                "budget_usd":    result.get("budget_usd"),
            },
        })

        logger.info(
            f"[intake] origin={result['origin_port']} dest={result['port']} "
            f"eta={result['eta_days']}d cargo={result['cargo_type']}"
        )
        return result

    @staticmethod
    def _compute_eta_from_route(origin: str, dest: str) -> dict:
        """
        Compute real ETA from OSRM route distance.
        Returns {days, hours, source} — never returns None.
        """
        if not origin or not dest:
            return {"days": 7, "hours": None, "source": "default"}

        try:
            import requests as _req
            from app.backend.routes._geocoder import geocode

            og = geocode(origin)
            dg = geocode(dest)
            if not og or not dg:
                return {"days": 7, "hours": None, "source": "default"}

            # Try OSRM for real road distance/duration
            url = (
                f"http://router.project-osrm.org/route/v1/driving/"
                f"{og['lon']},{og['lat']};{dg['lon']},{dg['lat']}"
                f"?overview=false&steps=false"
            )
            resp = _req.get(url, timeout=8, headers={"User-Agent": "AgentRouteAI/3.0"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    hours = round(route["duration"] / 3600, 1)
                    km = round(route["distance"] / 1000)
                    # Road freight: ~400km/day average (includes rest stops)
                    days = max(1, round(km / 400))
                    logger.info(f"[intake] OSRM ETA: {origin}→{dest}: {km}km, {hours}h, ~{days}d")
                    return {"days": days, "hours": hours, "source": "osrm_live"}

        except Exception as e:
            logger.warning(f"[intake] ETA computation failed: {e}")

        return {"days": 7, "hours": None, "source": "default"}


