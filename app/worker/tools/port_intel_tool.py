"""
app/tools/port_intel_tool.py — Port Intelligence Tool

Wraps PortIntelAgent as a self-describing tool.
Provides port operational data: congestion, wait times, labor, efficiency.
Blends static port profiles with live DB historical data.
"""
from .registry import Tool


def build_port_intel_tool(db_execute, config) -> Tool:
    from app.worker.agents.port_intel_agent import PortIntelAgent
    agent = PortIntelAgent(db_execute, config)

    def _run(**kw):
        return agent.run(kw["port"], kw["port_city"], kw["session_id"])

    return Tool(
        name="get_port_intel",
        description=(
            "Get port operational intelligence for the destination port. "
            "Data includes: congestion level (LOW/MEDIUM/HIGH), average berth wait hours, "
            "labor status, infrastructure rating, efficiency index, seasonal peak adjustments. "
            "Covers 10+ major global ports. No external API required. "
            "Use when: assessing port-side operational delays."
        ),
        agent_name="port_intel",
        func=_run,
        input_keys=["port", "port_city", "session_id"],
        output_keys=["congestion_level", "avg_wait_hours", "labor_status",
                     "efficiency_index", "port_score", "risk_signals"],
        requires_api_key=None,
        cache_ttl=7200,
        priority=3,
        is_parallel_safe=True,
    )

