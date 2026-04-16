"""
app/tools/vessel_tool.py — Vessel Tracking Tool

Wraps VesselAgent as a self-describing tool.
Tracks AIS position, ETA deviation, and route anomalies.
Falls back to intelligent route-based estimation when no AIS key.
"""
from .registry import Tool


def build_vessel_tool(db_execute, config) -> Tool:
    from app.worker.agents.vessel_agent import VesselAgent
    agent = VesselAgent(db_execute, config)

    def _run(**kw):
        return agent.run(
            kw.get("vessel_name"),
            kw.get("origin_port"),
            kw.get("dest_port"),
            kw.get("eta_days", 7),
            kw["session_id"],
        )

    return Tool(
        name="track_vessel",
        description=(
            "Track vessel position and ETA deviation using AIS (AISStream.io). "
            "Detects route anomalies, slow steaming, and rerouting events. "
            "Falls back to route-based intelligent estimation when API unavailable. "
            "Use when: vessel name is known, origin port specified, or ETA accuracy matters."
        ),
        agent_name="vessel",
        func=_run,
        input_keys=["vessel_name", "origin_port", "dest_port", "eta_days", "session_id"],
        output_keys=["vessel_status", "current_speed_knots", "eta_deviation_days",
                     "is_rerouted", "route_risk", "vessel_score", "risk_signals"],
        requires_api_key="AISSTREAM_API_KEY",
        cache_ttl=1800,
        priority=4,
        is_parallel_safe=True,
    )

