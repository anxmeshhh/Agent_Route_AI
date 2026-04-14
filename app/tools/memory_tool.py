"""
app/tools/memory_tool.py — Memory Recall Tool

Wraps MemoryAgent's recall capability as a self-describing tool.
Searches past analyses for similar port/cargo combinations.
Provides institutional learning — the system remembers what it learned.
"""
from .registry import Tool


def build_memory_tool(db_execute, config) -> Tool:
    from ..agents.memory import MemoryAgent
    agent = MemoryAgent(db_execute, config)

    def _run(**kw):
        return agent.recall(kw["port"], kw["cargo_type"], kw["session_id"])

    return Tool(
        name="search_memory",
        description=(
            "Search institutional memory for past analyses of similar shipments. "
            "Returns: similar past risk assessments for this port, cargo-type baseline risk, "
            "prediction accuracy (if outcomes were recorded), and learned patterns. "
            "Pure MySQL — no API cost. Enables the system to learn from experience. "
            "Use when: port is known — past context always improves confidence."
        ),
        agent_name="memory",
        func=_run,
        input_keys=["port", "cargo_type", "session_id"],
        output_keys=["similar_analyses", "memory_count", "prediction_accuracy",
                     "learned_patterns"],
        requires_api_key=None,
        cache_ttl=0,
        priority=2,
        is_parallel_safe=True,
    )
