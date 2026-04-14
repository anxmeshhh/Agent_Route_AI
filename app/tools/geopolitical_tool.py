"""
app/tools/geopolitical_tool.py — Geopolitical Risk Tool

Wraps GeopoliticalAgent as a self-describing tool.
Analyses sanctions, piracy zones, chokepoints, conflict areas on the route.
Fully deterministic — no external API needed.
"""
from .registry import Tool


def build_geopolitical_tool(db_execute, config) -> Tool:
    from ..agents.geopolitical_agent import GeopoliticalAgent
    agent = GeopoliticalAgent(db_execute, config)

    def _run(**kw):
        return agent.run(
            kw["port"],
            kw.get("origin_port"),
            kw.get("route_region"),
            kw["session_id"],
        )

    return Tool(
        name="assess_geopolitical",
        description=(
            "Assess geopolitical risk for the shipping route. "
            "Analyses: critical chokepoints (Suez, Hormuz, Bab-el-Mandeb, Malacca, Panama), "
            "regional conflict zones (Red Sea, Black Sea, Gulf of Guinea), "
            "OFAC/EU sanctions screening, piracy risk zones (IMB data). "
            "No external API — pure intelligence. "
            "Use when: route passes through politically sensitive or conflict regions."
        ),
        agent_name="geopolitical",
        func=_run,
        input_keys=["port", "origin_port", "route_region", "session_id"],
        output_keys=["region_risk", "chokepoints", "sanctions_risk",
                     "piracy_risk", "geo_score", "risk_signals"],
        requires_api_key=None,
        cache_ttl=43200,
        priority=4,
        is_parallel_safe=True,
    )
