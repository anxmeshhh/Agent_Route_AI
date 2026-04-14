"""
app/agents/intake_agent.py — Module 1

Parses a natural-language shipment query and extracts structured fields.
No LLM used — pure regex + keyword matching.
Direction-aware: correctly handles "from ORIGIN to DESTINATION" patterns.
"""
import re
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Known ports and weather-API city names ─────────────────────────────────────
PORT_MAP = {
    # Middle East
    "jebel ali":        ("Jebel Ali",          "Dubai"),
    "dubai":            ("Jebel Ali",          "Dubai"),
    "abu dhabi":        ("Abu Dhabi",           "Abu Dhabi"),
    "hamad":            ("Hamad Port",          "Doha"),
    "doha":             ("Hamad Port",          "Doha"),
    "salalah":          ("Salalah",             "Salalah"),
    "sohar":            ("Sohar",               "Sohar"),
    "aden":             ("Aden",                "Aden"),
    # Asia
    "singapore":        ("Singapore",           "Singapore"),
    "shanghai":         ("Shanghai",            "Shanghai"),
    "ningbo":           ("Ningbo",              "Ningbo"),
    "shenzhen":         ("Shenzhen",            "Shenzhen"),
    "hong kong":        ("Hong Kong",           "Hong Kong"),
    "guangzhou":        ("Guangzhou",           "Guangzhou"),
    "tianjin":          ("Tianjin",             "Tianjin"),
    "busan":            ("Busan",               "Busan"),
    "colombo":          ("Colombo",             "Colombo"),
    "nhava sheva":      ("Nhava Sheva",         "Mumbai"),
    "kolkata":          ("Kolkata",             "Kolkata"),
    "karachi":          ("Karachi",             "Karachi"),
    "klang":            ("Port Klang",          "Klang"),
    "tanjung pelepas":  ("Tanjung Pelepas",     "Johor Bahru"),
    # Europe
    "rotterdam":        ("Rotterdam",           "Rotterdam"),
    "antwerp":          ("Antwerp",             "Antwerp"),
    "hamburg":          ("Hamburg",             "Hamburg"),
    "felixstowe":       ("Felixstowe",          "Felixstowe"),
    "barcelona":        ("Barcelona",           "Barcelona"),
    "genoa":            ("Genoa",               "Genoa"),
    "piraeus":          ("Piraeus",             "Athens"),
    # Americas
    "los angeles":      ("Los Angeles",         "Los Angeles"),
    "long beach":       ("Long Beach",          "Long Beach"),
    "new york":         ("New York/New Jersey", "New York"),
    "savannah":         ("Savannah",            "Savannah"),
    "houston":          ("Houston",             "Houston"),
    "santos":           ("Santos",              "Santos"),
    "callao":           ("Callao",              "Lima"),
    # Africa
    "durban":           ("Durban",              "Durban"),
    "mombasa":          ("Mombasa",             "Mombasa"),
    "dar es salaam":    ("Dar es Salaam",       "Dar es Salaam"),
    "casablanca":       ("Casablanca",          "Casablanca"),
    "tanger med":       ("Tanger Med",          "Tangier"),
    "djibouti":         ("Djibouti",            "Djibouti"),
    # ── India land / maritime cities ──────────────────────────────
    "delhi":            ("Delhi",               "Delhi"),
    "new delhi":        ("New Delhi",           "Delhi"),
    "mumbai":           ("Mumbai",              "Mumbai"),
    "chennai":          ("Chennai",             "Chennai"),
    "bangalore":        ("Bangalore",           "Bangalore"),
    "bengaluru":        ("Bangalore",           "Bangalore"),
    "hyderabad":        ("Hyderabad",           "Hyderabad"),
    "pune":             ("Pune",                "Pune"),
    "ahmedabad":        ("Ahmedabad",           "Ahmedabad"),
    "jaipur":           ("Jaipur",              "Jaipur"),
    "lucknow":          ("Lucknow",             "Lucknow"),
    "nagpur":           ("Nagpur",              "Nagpur"),
    "surat":            ("Surat",               "Surat"),
    "kerala":           ("Thiruvananthapuram",  "Thiruvananthapuram"),
    "thiruvananthapuram": ("Thiruvananthapuram","Thiruvananthapuram"),
    "trivandrum":       ("Thiruvananthapuram",  "Thiruvananthapuram"),
    "kochi":            ("Kochi",               "Kochi"),
    "cochin":           ("Kochi",               "Kochi"),
    "coimbatore":       ("Coimbatore",          "Coimbatore"),
    "madurai":          ("Madurai",             "Madurai"),
    "visakhapatnam":    ("Visakhapatnam",       "Visakhapatnam"),
    "bhopal":           ("Bhopal",              "Bhopal"),
    "patna":            ("Patna",               "Patna"),
    "indore":           ("Indore",              "Indore"),
    "chandigarh":       ("Chandigarh",          "Chandigarh"),
    "amritsar":         ("Amritsar",            "Amritsar"),
    "varanasi":         ("Varanasi",            "Varanasi"),
    "guwahati":         ("Guwahati",            "Guwahati"),
    "bhubaneswar":      ("Bhubaneswar",         "Bhubaneswar"),
    "raipur":           ("Raipur",              "Raipur"),
}

CARGO_KEYWORDS = {
    "electronics":  ["electronics", "semiconductor", "chip", "pcb", "phones", "laptops"],
    "perishables":  ["perishable", "food", "fruit", "vegetable", "frozen", "cold chain", "refrigerated"],
    "pharmaceutical": ["pharma", "pharmaceutical", "medicine", "drug", "medical", "vaccine"],
    "automotive":   ["automotive", "car", "vehicle", "auto parts", "spare parts"],
    "chemicals":    ["chemicals", "hazmat", "dangerous goods", "flammable", "toxic"],
    "textiles":     ["textiles", "apparel", "clothing", "garments", "fabric"],
    "machinery":    ["machinery", "equipment", "heavy equipment", "industrial"],
    "oil_gas":      ["oil", "gas", "petroleum", "lng", "crude"],
    "general":      ["cargo", "goods", "shipment", "container", "freight"],
}


def _lookup_port(raw: str) -> tuple:
    """Returns (port_name, city) for the best matching PORT_MAP key, or (None, None)."""
    raw = raw.strip().lower()
    # Exact key match first
    if raw in PORT_MAP:
        return PORT_MAP[raw]
    # Substring match
    for kw, (pname, city) in PORT_MAP.items():
        if kw in raw or raw in kw or raw.startswith(kw) or kw.startswith(raw):
            return (pname, city)
    return (None, None)


class IntakeAgent:
    """
    Module 1: parse raw user query → structured shipment dict.
    Direction-aware: 'from ORIGIN to DESTINATION' is correctly split.
    """

    def run(self, query_text: str, session_id: Optional[str] = None) -> dict:
        if not session_id:
            session_id = str(uuid.uuid4())

        result = {
            "session_id":  session_id,
            "query_text":  query_text.strip(),
            "port":        None,   # destination port/city
            "port_city":   None,   # weather lookup city
            "eta_days":    None,
            "cargo_type":  "general",
            "vessel_name": None,
            "origin_port": None,
            "logs":        [],
        }

        text = query_text.strip()
        tl   = text.lower()
        logs = result["logs"]

        logs.append({"agent": "intake",
                     "action": "Parsing shipment query — direction-aware origin/destination extraction",
                     "status": "started"})

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
        # Used when Strategy A did not find a destination
        # ══════════════════════════════════════════════════════════
        if not result["port"]:
            to_pos = re.search(r"\bto\b", tl)
            scan   = tl[to_pos.start():] if to_pos else tl
            for kw, (pname, city) in PORT_MAP.items():
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
            for kw, (pname, _) in PORT_MAP.items():
                if kw in pre:
                    result["origin_port"] = pname
                    logs.append({"agent": "intake",
                                 "action": f"Origin via pre-'to' scan: {pname}",
                                 "status": "success"})
                    break

        # ══════════════════════════════════════════════════════════
        # STRATEGY D: smart default origin if still missing
        # ══════════════════════════════════════════════════════════
        if not result["origin_port"]:
            dl = (result["port"] or "").lower()
            cl = (result["port_city"] or "").lower()
            india_dests = ["thiruvananthapuram","kochi","chennai","bangalore","bengaluru",
                           "hyderabad","kolkata","pune","ahmedabad","mumbai","kerala",
                           "coimbatore","nagpur","jaipur","lucknow","bhubaneswar","visakhapatnam"]
            if any(ic in dl or ic in cl for ic in india_dests):
                result["origin_port"] = "Delhi"
            elif any(x in dl for x in ["rotterdam","hamburg","antwerp","felixstowe"]):
                result["origin_port"] = "Shanghai"
            elif any(x in dl for x in ["los angeles","long beach","seattle"]):
                result["origin_port"] = "Shenzhen"
            elif any(x in dl for x in ["jebel ali","dubai","doha"]):
                result["origin_port"] = "Singapore"
            else:
                result["origin_port"] = "Shanghai"
            logs.append({"agent": "intake",
                         "action": f"Origin defaulted to {result['origin_port']}",
                         "status": "skipped"})

        # Collision guard: origin must not equal destination
        if result["origin_port"] and result["port"] and \
           result["origin_port"].lower() == result["port"].lower():
            india_kw = ["thiruvananthapuram","kerala","bangalore","hyderabad","kochi","chennai"]
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
            result["eta_days"] = 7
            logs.append({"agent": "intake", "action": "ETA defaulted to 7 days", "status": "skipped"})

        # ══════════════════════════════════════════════════════════
        # CARGO TYPE
        # ══════════════════════════════════════════════════════════
        for ctype, kws in CARGO_KEYWORDS.items():
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
                "port":        result["port"],
                "port_city":   result["port_city"],
                "eta_days":    result["eta_days"],
                "cargo_type":  result["cargo_type"],
                "origin_port": result["origin_port"],
            },
        })

        logger.info(
            f"[intake] origin={result['origin_port']} dest={result['port']} "
            f"eta={result['eta_days']}d cargo={result['cargo_type']}"
        )
        return result
