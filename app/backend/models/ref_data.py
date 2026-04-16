"""
app/models/ref_data.py — DB-backed reference data loader

Loads ALL static reference tables from MySQL into an in-memory cache at
app startup. Agents and routing modules call get_*() instead of using
hardcoded dicts. Zero hardcoded values live here.
"""
import logging
import json

logger = logging.getLogger(__name__)

_CACHE: dict = {}


# ─── Public loader ────────────────────────────────────────────────────────────

def load_all(db_execute) -> None:
    """Load all reference tables into memory. Called once at app startup."""
    try:
        _load_ports(db_execute)
        _load_cargo_keywords(db_execute)
        _load_chokepoints(db_execute)
        _load_region_ports(db_execute)
        _load_sanctions(db_execute)
        _load_route_benchmarks(db_execute)
        _load_risk_keywords(db_execute)
        _load_default_origins(db_execute)
        # Routing tables
        _load_geocoords(db_execute)
        _load_maritime_routes(db_execute)
        _load_cost_rates(db_execute)
        _load_delay_bands(db_execute)
        _load_chokepoint_intel(db_execute)
        _load_maritime_alt_routes(db_execute)
        logger.info(
            f"[ref_data] \u2705 Loaded: {len(_CACHE.get('port_map', {}))} ports, "
            f"{len(_CACHE.get('geocoords', {}))} geocoords, "
            f"{len(_CACHE.get('chokepoints', {}))} chokepoints, "
            f"{len(_CACHE.get('route_benchmarks', {}))} route benchmarks, "
            f"{len(_CACHE.get('maritime_routes', {}))} maritime routes, "
            f"{len(_CACHE.get('cost_rates', {}))} cost rates, "
            f"{len(_CACHE.get('sanctions', []))} sanction entries"
        )
    except Exception as e:
        logger.error(f"[ref_data] \u274c Failed to load reference data: {e}")


def reload(db_execute) -> None:
    """Hot-reload all reference tables (admin route can call this)."""
    _CACHE.clear()
    load_all(db_execute)


# ─── Public accessors — Agent tables ─────────────────────────────────────────

def get_port_map() -> dict:
    """Returns {alias_key: (canonical_name, weather_city)} for all ports."""
    return _CACHE.get("port_map", {})


def get_port_profiles() -> dict:
    """Returns {alias_key: {profile fields}} for ports with baseline data."""
    return _CACHE.get("port_profiles", {})


def get_cargo_keywords() -> dict:
    """Returns {cargo_type: [keyword, ...]} mapping."""
    return _CACHE.get("cargo_keywords", {})


def get_chokepoints() -> dict:
    """Returns {key_name: {chokepoint fields}} dict."""
    return _CACHE.get("chokepoints", {})


def get_region_ports() -> dict:
    """Returns {region_key: [port_name, ...]} dict."""
    return _CACHE.get("region_ports", {})


def get_piracy_zones() -> list:
    """Returns list of region_key strings that are piracy zones."""
    return _CACHE.get("piracy_zones", [])


def get_region_risk_levels() -> dict:
    """Returns {region_key: risk_level} dict."""
    return _CACHE.get("region_risk_levels", {})


def get_sanctions() -> list:
    """Returns list of lowercase country name strings."""
    return _CACHE.get("sanctions", [])


def get_route_benchmarks() -> dict:
    """Returns {(origin_key, dest_key): {benchmark fields}} dict."""
    return _CACHE.get("route_benchmarks", {})


def get_cape_extra_days() -> int:
    """Returns the configured Cape-of-Good-Hope extra days constant."""
    return _CACHE.get("cape_extra_days", 14)


def get_risk_keywords(category: str) -> list:
    """
    Returns keyword list for a given category.
    Categories: 'geo_high', 'geo_medium', 'port_strike', 'port_closure',
                'port_congestion', 'vessel_reroute', 'vessel_delay', 'vessel_early'
    """
    return _CACHE.get("risk_keywords", {}).get(category, [])


def get_default_origins() -> dict:
    """Returns {dest_keyword: default_origin} dict."""
    return _CACHE.get("default_origins", {})


# ─── Public accessors — Routing tables ───────────────────────────────────────

def get_geocoords() -> dict:
    """Returns {name_key: {lat, lon, display, coord_type, iata_code, snap_radius_km}}."""
    return _CACHE.get("geocoords", {})


def get_airports() -> dict:
    """Returns only airport entries from geocoords: {name_key: {...}}."""
    return {k: v for k, v in _CACHE.get("geocoords", {}).items()
            if v.get("coord_type") == "airport"}


def get_road_checkpoints() -> dict:
    """Returns road_hub entries as {display_name: [lat, lon]} for _CHECKPOINTS drop-in."""
    return _CACHE.get("road_checkpoints", {})


def get_maritime_routes() -> dict:
    """Returns {(origin_region, dest_region): [chokepoint_coord_dicts]}."""
    return _CACHE.get("maritime_routes", {})


def get_cost_rates() -> dict:
    """Returns {(transport_mode, cargo_type): {daily_cost_usd, cost_source}}."""
    return _CACHE.get("cost_rates", {})


def get_delay_bands() -> list:
    """Returns list (desc by score) of {risk_score_min, risk_score_max, delay_probability, expected_delay_days}."""
    return _CACHE.get("delay_bands", [])


def get_chokepoint_intel() -> dict:
    """Returns {key_name: {why, saves, risk, intel_source}}."""
    return _CACHE.get("chokepoint_intel", {})


def get_maritime_alt_routes() -> dict:
    """Returns {trigger_key: {via_label, reason, when_to_choose, waypoints, km_per_day}}."""
    return _CACHE.get("maritime_alt_routes", {})


def is_loaded() -> bool:
    """Returns True if reference data has been successfully loaded."""
    return bool(_CACHE.get("port_map"))


# ─── Private loaders — Agent tables ──────────────────────────────────────────

def _load_ports(db_execute) -> None:
    rows = db_execute(
        "SELECT alias_key, canonical_name, weather_city, region, "
        "capacity_teu, avg_wait_hours, congestion_base, labor_risk, "
        "infrastructure, efficiency_index, peak_months "
        "FROM ref_ports",
        fetch=True
    )
    port_map = {}
    port_profiles = {}
    for r in (rows or []):
        key = r["alias_key"].lower()
        port_map[key] = (r["canonical_name"], r["weather_city"] or r["canonical_name"])
        if r.get("capacity_teu"):
            try:
                peak = json.loads(r["peak_months"] or "[]")
            except (json.JSONDecodeError, TypeError):
                peak = []
            port_profiles[key] = {
                "region":              r["region"] or "Unknown",
                "capacity_teu":        r["capacity_teu"],
                "avg_wait_hours":      r["avg_wait_hours"] or 18,
                "congestion_baseline": r["congestion_base"] or "MEDIUM",
                "labor_risk":          r["labor_risk"] or "MEDIUM",
                "infrastructure":      r["infrastructure"] or "MODERATE",
                "efficiency_index":    float(r["efficiency_index"] or 0.80),
                "peak_months":         peak,
            }
    _CACHE["port_map"]      = port_map
    _CACHE["port_profiles"] = port_profiles


def _load_cargo_keywords(db_execute) -> None:
    rows = db_execute(
        "SELECT cargo_type, keyword FROM ref_cargo_keywords ORDER BY cargo_type",
        fetch=True
    )
    result: dict = {}
    for r in (rows or []):
        result.setdefault(r["cargo_type"], []).append(r["keyword"])
    _CACHE["cargo_keywords"] = result


def _load_chokepoints(db_execute) -> None:
    rows = db_execute(
        "SELECT key_name, display_name, search_query, base_score, risk_level, "
        "routes_eu_asia, routes_eu_me, routes_me_any, routes_se_asia, "
        "routes_americas, routes_black_sea "
        "FROM ref_chokepoints",
        fetch=True
    )
    result = {}
    for r in (rows or []):
        result[r["key_name"]] = {
            "name":            r["display_name"],
            "search_query":    r["search_query"],
            "base_score":      r["base_score"],
            "risk_level":      r["risk_level"],
            "routes_eu_asia":  bool(r["routes_eu_asia"]),
            "routes_eu_me":    bool(r["routes_eu_me"]),
            "routes_me_any":   bool(r["routes_me_any"]),
            "routes_se_asia":  bool(r["routes_se_asia"]),
            "routes_americas": bool(r["routes_americas"]),
            "routes_black_sea":bool(r["routes_black_sea"]),
        }
    _CACHE["chokepoints"] = result


def _load_region_ports(db_execute) -> None:
    rows = db_execute(
        "SELECT region_key, port_name, is_piracy_zone, risk_level "
        "FROM ref_region_ports ORDER BY region_key",
        fetch=True
    )
    region_ports: dict = {}
    piracy_zones: list = []
    risk_levels:  dict = {}
    for r in (rows or []):
        rk = r["region_key"]
        region_ports.setdefault(rk, []).append(r["port_name"])
        if r.get("is_piracy_zone") and rk not in piracy_zones:
            piracy_zones.append(rk)
        if r.get("risk_level"):
            risk_levels[rk] = r["risk_level"]
    _CACHE["region_ports"]       = region_ports
    _CACHE["piracy_zones"]       = piracy_zones
    _CACHE["region_risk_levels"] = risk_levels


def _load_sanctions(db_execute) -> None:
    rows = db_execute("SELECT country_name FROM ref_sanctions", fetch=True)
    _CACHE["sanctions"] = [r["country_name"].lower() for r in (rows or [])]


def _load_route_benchmarks(db_execute) -> None:
    rows = db_execute(
        "SELECT origin_key, dest_key, via_route, normal_days, "
        "buffer_days, cape_extra_days FROM ref_route_benchmarks",
        fetch=True
    )
    result = {}
    cape = 14
    for r in (rows or []):
        key = (r["origin_key"].lower(), r["dest_key"].lower())
        result[key] = {
            "via":         r["via_route"] or "Direct",
            "normal_days": r["normal_days"],
            "buffer_days": float(r["buffer_days"]),
        }
        if r.get("cape_extra_days"):
            cape = r["cape_extra_days"]
    _CACHE["route_benchmarks"] = result
    _CACHE["cape_extra_days"]   = cape


def _load_risk_keywords(db_execute) -> None:
    rows = db_execute(
        "SELECT keyword, severity, category FROM ref_risk_keywords", fetch=True
    )
    result: dict = {}
    for r in (rows or []):
        result.setdefault(r["category"], []).append(r["keyword"])
    _CACHE["risk_keywords"] = result


def _load_default_origins(db_execute) -> None:
    rows = db_execute(
        "SELECT dest_keyword, default_origin FROM ref_default_origins", fetch=True
    )
    _CACHE["default_origins"] = {
        r["dest_keyword"].lower(): r["default_origin"]
        for r in (rows or [])
    }


# ─── Private loaders — Routing tables ────────────────────────────────────────

def _load_geocoords(db_execute) -> None:
    rows = db_execute(
        "SELECT name_key, display, lat, lon, coord_type, iata_code, snap_radius_km "
        "FROM ref_geocoords",
        fetch=True
    )
    geocoords = {}
    road_checkpoints = {}
    for r in (rows or []):
        key = r["name_key"].lower()
        entry = {
            "lat":            float(r["lat"]),
            "lon":            float(r["lon"]),
            "display":        r["display"],
            "coord_type":     r["coord_type"],
            "iata_code":      r.get("iata_code"),
            "snap_radius_km": r.get("snap_radius_km", 35),
        }
        geocoords[key] = entry
        if r["coord_type"] == "road_hub":
            road_checkpoints[r["display"]] = [float(r["lat"]), float(r["lon"])]
    _CACHE["geocoords"]        = geocoords
    _CACHE["road_checkpoints"] = road_checkpoints


def _load_maritime_routes(db_execute) -> None:
    """Load route table and resolve chokepoint name_keys to coord dicts."""
    rows = db_execute(
        "SELECT origin_region, dest_region, chokepoint_keys FROM ref_maritime_routes",
        fetch=True
    )
    geocoords = _CACHE.get("geocoords", {})
    result = {}
    for r in (rows or []):
        try:
            keys = json.loads(r["chokepoint_keys"] or "[]")
        except (json.JSONDecodeError, TypeError):
            keys = []
        resolved = []
        for k in keys:
            entry = geocoords.get(k.lower())
            if entry:
                resolved.append({
                    "lat":  entry["lat"],
                    "lon":  entry["lon"],
                    "name": entry["display"],
                })
            else:
                logger.warning(f"[ref_data] Maritime route: unknown key '{k}'")
        result[(r["origin_region"], r["dest_region"])] = resolved
    _CACHE["maritime_routes"] = result


def _load_cost_rates(db_execute) -> None:
    rows = db_execute(
        "SELECT transport_mode, cargo_type, daily_cost_usd, cost_source "
        "FROM ref_cost_rates",
        fetch=True
    )
    result = {}
    for r in (rows or []):
        result[(r["transport_mode"], r["cargo_type"])] = {
            "daily_cost_usd": r["daily_cost_usd"],
            "cost_source":    r.get("cost_source", ""),
        }
    _CACHE["cost_rates"] = result


def _load_delay_bands(db_execute) -> None:
    rows = db_execute(
        "SELECT risk_score_min, risk_score_max, delay_probability, expected_delay_days "
        "FROM ref_delay_bands ORDER BY risk_score_min DESC",
        fetch=True
    )
    result = []
    for r in (rows or []):
        result.append({
            "risk_score_min":      r["risk_score_min"],
            "risk_score_max":      r["risk_score_max"],
            "delay_probability":   float(r["delay_probability"]),
            "expected_delay_days": float(r["expected_delay_days"]),
        })
    _CACHE["delay_bands"] = result


def _load_chokepoint_intel(db_execute) -> None:
    rows = db_execute(
        "SELECT key_name, why_chosen, saves, risk_notes, intel_source "
        "FROM ref_chokepoint_intel",
        fetch=True
    )
    result = {}
    for r in (rows or []):
        result[r["key_name"]] = {
            "why":          r["why_chosen"],
            "saves":        r.get("saves", ""),
            "risk":         r.get("risk_notes", ""),
            "intel_source": r.get("intel_source", ""),
        }
    _CACHE["chokepoint_intel"] = result


def _load_maritime_alt_routes(db_execute) -> None:
    rows = db_execute(
        "SELECT trigger_key, via_label, reason, when_to_choose, waypoints_json, km_per_day "
        "FROM ref_maritime_alt_routes",
        fetch=True
    )
    result = {}
    for r in (rows or []):
        try:
            wps = json.loads(r["waypoints_json"] or "[]")
        except (json.JSONDecodeError, TypeError):
            wps = []
        result[r["trigger_key"]] = {
            "via_label":      r["via_label"],
            "reason":         r.get("reason", ""),
            "when_to_choose": r.get("when_to_choose", ""),
            "waypoints":      wps,
            "km_per_day":     r.get("km_per_day", 550),
        }
    _CACHE["maritime_alt_routes"] = result
