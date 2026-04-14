"""
app/tools/weather_tool.py — Weather Tool

Wraps WeatherAgent as a self-describing tool.
Fetches real-time conditions from OpenWeatherMap (with MySQL cache).
"""
from .registry import Tool


def build_weather_tool(db_execute, config) -> Tool:
    from ..agents.weather_agent import WeatherAgent
    agent = WeatherAgent(db_execute, config)

    def _run(**kw):
        return agent.run(kw["port_city"], kw["session_id"])

    return Tool(
        name="fetch_weather",
        description=(
            "Fetch live weather conditions for a port city using OpenStreetMap "
            "and Open-Meteo. Returns wind speed, visibility, conditions, temperature, and "
            "derived weather risk signals. Results cached 1 hour in MySQL. "
            "Use when: ETA < 7 days, weather-sensitive cargo, tropical/storm-prone regions."
        ),
        agent_name="weather",
        func=_run,
        input_keys=["port_city", "session_id"],
        output_keys=["conditions", "wind_speed", "temperature", "weather_score", "risk_signals"],
        requires_api_key=None,  # Open-Meteo is free/doesn't require a key
        cache_ttl=3600,
        priority=2,
        is_parallel_safe=True,
    )
