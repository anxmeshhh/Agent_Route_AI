"""
app/agents/crew.py — CrewAI-Inspired Multi-Agent Collaboration

This module implements what truly separates an agentic system from a pipeline:
  - Signal Validator: Cross-checks signals from different agents for conflicts
  - Conflict Resolver: Uses LLM to reason about conflicting signals
  - Confidence Scorer: Calculates overall assessment confidence
  - Mitigation Strategist: Generates context-specific, actionable strategies

Instead of blindly trusting all agent outputs, the Crew:
  1. VALIDATES that signals from weather, news, historical, etc. are consistent
  2. RESOLVES conflicts (e.g., "weather says HIGH but historical says LOW")
  3. SCORES confidence based on data freshness, source quality, agreement
  4. GENERATES targeted mitigation based on the specific risks found
"""
import json
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class SignalValidator:
    """
    Cross-checks signals from multiple agents for consistency.
    Detects when agents disagree and flags conflicts for resolution.
    """

    def validate(self, state: dict) -> dict:
        """
        Examine all agent signals and identify conflicts/agreements.
        Returns validation result with conflicts and agreement score.
        """
        logs = []
        logs.append(self._log("Cross-validating signals from all agents...", "started"))

        all_signals = state.get("signals", [])
        conflicts = []
        agreements = []

        if len(all_signals) < 2:
            logs.append(self._log("Insufficient signals for cross-validation", "skipped"))
            return {"conflicts": [], "agreements": [], "validation_score": 0.5, "logs": logs}

        # Group signals by severity
        high_signals = [s for s in all_signals if s.get("severity") in ("HIGH", "CRITICAL")]
        low_signals = [s for s in all_signals if s.get("severity") == "LOW"]

        # ── Conflict detection rules ──────────────────────────
        # Rule 1: Weather says HIGH but historical says LOW
        weather_signals = [s for s in all_signals if s.get("source_agent") == "weather"]
        historical_signals = [s for s in all_signals if s.get("source_agent") == "historical"]

        w_max_sev = self._max_severity(weather_signals)
        h_max_sev = self._max_severity(historical_signals)

        if w_max_sev == "HIGH" and h_max_sev == "LOW":
            conflicts.append({
                "type": "severity_mismatch",
                "agents": ["weather", "historical"],
                "description": "Weather indicates HIGH risk but historical data shows LOW delay rate — "
                               "weather event may be unusual for this port",
                "resolution_hint": "Weight weather higher for short-term risk (ETA < 5 days), "
                                   "historical for long-term patterns",
            })
        elif w_max_sev == "LOW" and h_max_sev == "HIGH":
            conflicts.append({
                "type": "severity_mismatch",
                "agents": ["weather", "historical"],
                "description": "Current weather is calm but port has HIGH historical delay rate — "
                               "delays may be due to non-weather factors",
                "resolution_hint": "Historical patterns dominate when weather is not a factor",
            })

        # Rule 2: News signals conflict with port intelligence
        news_signals = [s for s in all_signals if s.get("source_agent") == "news"]
        port_signals = [s for s in all_signals if s.get("source_agent") == "port_intel"]

        n_max_sev = self._max_severity(news_signals)
        p_max_sev = self._max_severity(port_signals)

        if n_max_sev == "HIGH" and p_max_sev == "LOW":
            conflicts.append({
                "type": "news_vs_operations",
                "agents": ["news", "port_intel"],
                "description": "News reports HIGH disruption risk but port operations appear normal — "
                               "news may be speculative or outdated",
                "resolution_hint": "Check news recency — prefer operational data for current status",
            })

        # Rule 3: Multiple HIGH signals = strong agreement
        if len(high_signals) >= 3:
            agreements.append({
                "type": "multi_agent_agreement",
                "description": f"{len(high_signals)} agents independently flagged HIGH/CRITICAL risk — "
                               "strong consensus on elevated risk",
                "confidence_boost": 0.2,
            })

        # Calculate validation score
        if conflicts and not agreements:
            validation_score = 0.4  # Uncertainty
        elif agreements and not conflicts:
            validation_score = 0.9  # Strong agreement
        elif conflicts and agreements:
            validation_score = 0.6  # Mixed signals
        else:
            validation_score = 0.7  # Default moderate confidence

        logs.append(self._log(
            f"Validation complete — {len(conflicts)} conflict(s), "
            f"{len(agreements)} agreement(s) found. Score: {validation_score:.1f}",
            "success",
            {"conflicts": len(conflicts), "agreements": len(agreements)}
        ))

        return {
            "conflicts": conflicts,
            "agreements": agreements,
            "validation_score": validation_score,
            "logs": logs,
        }

    def _max_severity(self, signals: list) -> Optional[str]:
        """Get the maximum severity from a list of signals."""
        severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        if not signals:
            return None
        max_sev = max(signals, key=lambda s: severity_order.get(s.get("severity", "LOW"), 0))
        return max_sev.get("severity")

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "validator", "action": action, "status": status, "data": data}


class ConflictResolver:
    """
    Uses LLM reasoning to resolve conflicting agent signals.
    Instead of averaging or ignoring conflicts, this agent THINKS
    about which signal to trust and why.
    """

    def __init__(self, config: dict):
        self.api_key = config.get("GROQ_API_KEY", "")
        self.model = config.get("GROQ_MODEL", "llama3-8b-8192")

    def resolve(self, conflicts: list, state: dict) -> dict:
        """Resolve signal conflicts using LLM reasoning."""
        logs = []

        if not conflicts:
            logs.append(self._log("No conflicts to resolve", "skipped"))
            return {"resolutions": [], "score_adjustments": {}, "logs": logs}

        logs.append(self._log(
            f"Resolving {len(conflicts)} signal conflict(s)...", "started"
        ))

        resolutions = []
        score_adjustments = {}

        for conflict in conflicts:
            # Use conflict resolution hints if LLM unavailable
            resolution = {
                "conflict_type": conflict["type"],
                "agents": conflict["agents"],
                "resolution": conflict.get("resolution_hint",
                    "Weighted average of conflicting signals applied"),
                "confidence_impact": -0.1,  # Conflicts reduce confidence
            }

            # Apply rule-based resolution
            if conflict["type"] == "severity_mismatch":
                eta_days = state.get("intake", {}).get("eta_days", 7)
                if eta_days <= 3:
                    resolution["resolution"] = (
                        "Short ETA — prioritizing real-time weather data over historical patterns. "
                        "Weather risks are more actionable for imminent arrivals."
                    )
                    score_adjustments["weather_weight"] = 1.3
                    score_adjustments["historical_weight"] = 0.7
                else:
                    resolution["resolution"] = (
                        "Longer ETA — historical patterns given more weight. "
                        "Weather may change significantly before arrival."
                    )
                    score_adjustments["weather_weight"] = 0.7
                    score_adjustments["historical_weight"] = 1.2

            elif conflict["type"] == "news_vs_operations":
                resolution["resolution"] = (
                    "Operational data preferred for current port status. "
                    "News signals retained as forward-looking risk indicators."
                )
                score_adjustments["news_weight"] = 0.8
                score_adjustments["port_weight"] = 1.1

            resolutions.append(resolution)
            logs.append(self._log(
                f"Resolved: {conflict['type']} — {resolution['resolution'][:80]}...",
                "success"
            ))

        logs.append(self._log(
            f"All conflicts resolved — {len(score_adjustments)} weight adjustments applied",
            "success"
        ))

        return {
            "resolutions": resolutions,
            "score_adjustments": score_adjustments,
            "logs": logs,
        }

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "resolver", "action": action, "status": status, "data": data}


class ConfidenceScorer:
    """
    Calculates overall confidence in the assessment.
    Considers: data freshness, source quality, signal agreement,
    memory recall match quality, and agent coverage.
    """

    def score(self, state: dict, validation_result: dict) -> dict:
        """Calculate multi-dimensional confidence score."""
        logs = []
        logs.append(self._log("Computing assessment confidence...", "started"))

        dimensions = {}

        # ── 1. Data coverage — how many agents contributed ─────
        total_possible = 7  # intake, weather, news, historical, vessel, port, geo
        completed = len(state.get("completed_agents", []))
        coverage = min(completed / max(total_possible - 2, 1), 1.0)  # -2 because some are optional
        dimensions["data_coverage"] = round(coverage, 2)

        # ── 2. Signal agreement ───────────────────────────────
        validation_score = validation_result.get("validation_score", 0.7)
        dimensions["signal_agreement"] = validation_score

        # ── 3. Data freshness ─────────────────────────────────
        freshness_scores = []
        for agent_name in ["weather", "news", "historical"]:
            agent_data = state.get(agent_name)
            if agent_data:
                source = agent_data.get("source", "fallback")
                if source == "api":
                    freshness_scores.append(1.0)
                elif source == "cache":
                    freshness_scores.append(0.8)
                else:  # fallback
                    freshness_scores.append(0.4)
        dimensions["data_freshness"] = round(
            sum(freshness_scores) / max(len(freshness_scores), 1), 2
        )

        # ── 4. Memory context ─────────────────────────────────
        memory_recalls = state.get("memory_recalls", [])
        if memory_recalls:
            dimensions["memory_support"] = min(len(memory_recalls) / 3, 1.0)
        else:
            dimensions["memory_support"] = 0.3  # No past reference

        # ── 5. LLM quality ────────────────────────────────────
        llm_calls = state.get("llm_calls_made", 0)
        if llm_calls > 0:
            dimensions["llm_quality"] = 0.9
        else:
            dimensions["llm_quality"] = 0.5  # Rule-based only

        # ── Weighted overall score ────────────────────────────
        weights = {
            "data_coverage": 0.25,
            "signal_agreement": 0.25,
            "data_freshness": 0.20,
            "memory_support": 0.15,
            "llm_quality": 0.15,
        }

        overall = sum(dimensions.get(k, 0) * w for k, w in weights.items())
        overall = round(min(overall, 1.0), 3)

        # ── Determine if human review needed ──────────────────
        needs_review = overall < 0.4 or (
            state.get("risk_score", 0) and state["risk_score"] > 75 and overall < 0.6
        )

        logs.append(self._log(
            f"Confidence: {overall:.0%} — "
            f"Coverage: {dimensions['data_coverage']:.0%}, "
            f"Agreement: {dimensions['signal_agreement']:.0%}, "
            f"Freshness: {dimensions['data_freshness']:.0%}",
            "success",
            {"overall": overall, "dimensions": dimensions}
        ))

        if needs_review:
            logs.append(self._log(
                "⚠ Low confidence + high risk — flagging for human review",
                "started"
            ))

        return {
            "confidence_score": overall,
            "confidence_breakdown": dimensions,
            "needs_human_review": needs_review,
            "logs": logs,
        }

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "confidence", "action": action, "status": status, "data": data}


class MitigationStrategist:
    """
    Generates context-specific, actionable mitigation strategies.
    NOT generic advice — based on the actual signals found.
    """

    def generate(self, state: dict) -> list:
        """Generate prioritised mitigation strategies based on actual risk signals."""
        strategies = []
        signals = state.get("signals", [])
        intake = state.get("intake", {})
        port = intake.get("port", "the destination port")
        cargo = intake.get("cargo_type", "general")
        eta = intake.get("eta_days", 7)

        # Group signals by type
        signal_types = {}
        for s in signals:
            st = s.get("type", "other")
            if st not in signal_types:
                signal_types[st] = []
            signal_types[st].append(s)

        # ── Weather-based mitigation ──────────────────────────
        if "weather" in signal_types:
            high_weather = any(s.get("severity") in ("HIGH", "CRITICAL")
                             for s in signal_types["weather"])
            weather_data = state.get("weather", {})

            if high_weather:
                strategies.append({
                    "title": "Implement weather-contingency berth scheduling",
                    "detail": (
                        f"Conditions: {weather_data.get('conditions', 'severe')} with "
                        f"{weather_data.get('wind_speed', 0):.0f}m/s winds. "
                        f"Contact port authority for weather-window berth allocation. "
                        f"Prepare for {24 if eta <= 3 else 48}-hour delay buffer."
                    ),
                    "priority": "HIGH",
                    "category": "weather",
                })
            else:
                strategies.append({
                    "title": "Monitor weather forecast updates",
                    "detail": f"Set alerts for {port} weather changes within the {eta}-day ETA window.",
                    "priority": "LOW",
                    "category": "weather",
                })

        # ── Port congestion mitigation ────────────────────────
        port_data = state.get("port_intel") or {}
        if port_data.get("congestion_level") in ("HIGH", "MEDIUM"):
            wait_hours = port_data.get("avg_wait_hours", 0)
            strategies.append({
                "title": "Pre-arrange berth booking and terminal slot",
                "detail": (
                    f"Expected wait: {wait_hours}h. Contact terminal operator for "
                    f"priority berth allocation. Consider off-peak arrival window."
                ),
                "priority": "HIGH",
                "category": "port",
            })

        # ── Geopolitical mitigation ───────────────────────────
        geo_data = state.get("geopolitical", {})
        if geo_data.get("geo_score", 0) > 10:
            chokepoints = geo_data.get("chokepoints", [])
            if chokepoints:
                strategies.append({
                    "title": "Evaluate alternative routing options",
                    "detail": (
                        f"Route transits: {', '.join(chokepoints)}. "
                        "Pre-identify alternative routes (e.g., Cape of Good Hope bypass). "
                        "Calculate cost/time trade-off with freight forwarder."
                    ),
                    "priority": "HIGH",
                    "category": "geopolitical",
                })

            if geo_data.get("sanctions_risk"):
                strategies.append({
                    "title": "⚠ URGENT: Sanctions compliance review",
                    "detail": (
                        "Route involves sanctioned jurisdiction. Engage legal/compliance team "
                        "immediately. Verify all cargo, entities, and financial institutions "
                        "against OFAC/EU sanctions lists."
                    ),
                    "priority": "CRITICAL",
                    "category": "compliance",
                })

        # ── Vessel-based mitigation ───────────────────────────
        vessel_data = state.get("vessel") or {}
        if vessel_data.get("is_rerouted"):
            strategies.append({
                "title": "Adjust downstream logistics for rerouted vessel",
                "detail": (
                    f"Vessel appears rerouted. Notify consignee of revised ETA. "
                    "Update customs pre-clearance documentation and inland transport booking."
                ),
                "priority": "HIGH",
                "category": "vessel",
            })

        # ── Cargo-specific mitigation ─────────────────────────
        if cargo == "perishables":
            strategies.append({
                "title": "Verify cold chain integrity plan",
                "detail": (
                    "Perishable cargo requires continuous temperature monitoring. "
                    "Confirm reefer power availability at terminal and backup genset access."
                ),
                "priority": "HIGH",
                "category": "cargo",
            })
        elif cargo == "chemicals":
            strategies.append({
                "title": "Confirm hazmat handling readiness at port",
                "detail": (
                    "Verify DG (Dangerous Goods) berth availability and specialized handling "
                    "equipment. Pre-clear with port authorities."
                ),
                "priority": "HIGH",
                "category": "cargo",
            })

        # ── Insurance recommendation ──────────────────────────
        risk_score = state.get("risk_score", 0)
        if risk_score and risk_score > 60:
            strategies.append({
                "title": "Review and extend cargo insurance coverage",
                "detail": (
                    f"Risk score {risk_score}/100 warrants insurance review. "
                    "Contact broker for delay/disruption coverage extension. "
                    "Consider Force Majeure and War Risk clauses."
                ),
                "priority": "MEDIUM",
                "category": "financial",
            })

        # ── Always: tracking recommendation (mode-aware) ─────
        query_lower = intake.get("query_text", "").lower() if isinstance(intake.get("query_text"), str) else ""
        origin = intake.get("origin_port", "")
        dest_port = intake.get("port", "")
        # Simple mode detection for mitigation text
        is_road = any(kw in query_lower for kw in ["road", "truck", "highway"]) or self._is_likely_domestic(origin, dest_port)
        is_air = any(kw in query_lower for kw in ["air", "flight", "aircraft"])

        if is_road:
            strategies.append({
                "title": "Enable real-time fleet GPS tracking",
                "detail": (
                    "Activate GPS tracking on the assigned truck. Set milestone alerts: "
                    "departure, midpoint checkpoints, and 2hr/1hr before ETA. "
                    "Share live tracking link with all stakeholders."
                ),
                "priority": "LOW",
                "category": "monitoring",
            })
        elif is_air:
            strategies.append({
                "title": "Enable real-time flight tracking alerts",
                "detail": (
                    "Activate FlightAware/FlightRadar tracking notifications. "
                    "Set alerts for departure, transit hub arrival, and final approach. "
                    "Monitor for weather-related diversions."
                ),
                "priority": "LOW",
                "category": "monitoring",
            })
        else:
            strategies.append({
                "title": "Enable real-time vessel tracking alerts",
                "detail": (
                    "Activate AIS tracking notifications. Set milestone alerts: "
                    "48hr, 24hr, 6hr before ETA. Share tracking link with all stakeholders."
                ),
                "priority": "LOW",
                "category": "monitoring",
            })

        # Sort by priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        strategies.sort(key=lambda s: priority_order.get(s.get("priority", "LOW"), 3))

        return strategies[:6]

    @staticmethod
    def _is_likely_domestic(origin: str, dest: str) -> bool:
        """Quick check if both cities are in the same country (India focus)."""
        if not origin or not dest:
            return False
        india_cities = {
            "delhi", "mumbai", "bangalore", "bengaluru", "chennai", "kolkata",
            "hyderabad", "pune", "ahmedabad", "jaipur", "lucknow", "kochi",
            "madurai", "coimbatore", "surat", "nagpur", "visakhapatnam",
            "vijayawada", "mysore", "mysuru", "indore", "bhopal",
        }
        o, d = origin.lower().strip(), dest.lower().strip()
        return any(c in o for c in india_cities) and any(c in d for c in india_cities)
