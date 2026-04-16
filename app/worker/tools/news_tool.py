"""
app/tools/news_tool.py — News Tool

Wraps NewsAgent as a self-describing tool.
Searches NewsAPI for port disruptions, labor strikes, geopolitical events.
"""
from .registry import Tool


def build_news_tool(db_execute, config) -> Tool:
    from app.worker.agents.news_agent import NewsAgent
    agent = NewsAgent(db_execute, config)

    def _run(**kw):
        return agent.run(kw["port"], kw["port_city"], kw["session_id"])

    return Tool(
        name="search_news",
        description=(
            "Search real-time news articles for port disruptions, labor strikes, "
            "geopolitical events, and shipping alerts. Uses Tavily API. "
            "Results cached 6 hours in MySQL to preserve free-tier API limits. "
            "Use when: any port analysis — news context is always valuable for risk."
        ),
        agent_name="news",
        func=_run,
        input_keys=["port", "port_city", "session_id"],
        output_keys=["articles", "article_count", "news_score", "risk_signals"],
        requires_api_key="TAVILY_API_KEY",
        cache_ttl=21600,
        priority=3,
        is_parallel_safe=True,
    )

