"""
app/tools/historical_tool.py — Historical Data Tool

Wraps HistoricalAgent as a self-describing tool.
Queries MySQL historical_shipments table for delay patterns.
"""
from .registry import Tool


def build_historical_tool(db_execute, config) -> Tool:
    from ..agents.historical_agent import HistoricalAgent
    agent = HistoricalAgent(db_execute, config)

    def _run(**kw):
        return agent.run(
            kw["port"], kw["eta_days"], kw["cargo_type"], kw["session_id"]
        )

    return Tool(
        name="query_historical",
        description=(
            "Query the MySQL historical shipments database for port-specific delay patterns. "
            "Returns: delay rate %, average delay days, seasonal risk factors, cargo-type "
            "patterns, and risk signals. Pure SQL — no external API, no cost. "
            "Use ALWAYS — historical context is the foundation of any risk assessment."
        ),
        agent_name="historical",
        func=_run,
        input_keys=["port", "eta_days", "cargo_type", "session_id"],
        output_keys=["delay_rate", "avg_delay_days", "records_analysed",
                     "historical_score", "seasonal_risk", "risk_signals"],
        requires_api_key=None,
        cache_ttl=0,
        priority=1,          # Highest — always run first
        is_parallel_safe=True,
    )
