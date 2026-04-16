"""
app/tools/registry.py — Tool Registry

Central registry that discovers and holds all tools.
Each tool is defined in its own file (weather_tool.py, news_tool.py, etc.)
and registered here. The Brain Router queries tool schemas to decide
which tools are relevant for a given shipment query.
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Tool:
    """A self-describing tool that an agent can invoke."""

    def __init__(self, name, description, agent_name, func,
                 input_keys, output_keys, cost_per_call=0.0,
                 requires_api_key=None, cache_ttl=0,
                 priority=5, is_parallel_safe=True):
        self.name = name
        self.description = description
        self.agent_name = agent_name
        self.func = func
        self.input_keys = input_keys
        self.output_keys = output_keys
        self.cost_per_call = cost_per_call
        self.requires_api_key = requires_api_key
        self.cache_ttl = cache_ttl
        self.priority = priority
        self.is_parallel_safe = is_parallel_safe

    def to_schema(self) -> dict:
        """Return JSON-serializable schema for LLM routing decisions."""
        return {
            "name": self.name,
            "description": self.description,
            "agent": self.agent_name,
            "inputs": self.input_keys,
            "outputs": self.output_keys,
            "cost_per_call": self.cost_per_call,
            "requires_api_key": self.requires_api_key,
            "cache_ttl_seconds": self.cache_ttl,
            "priority": self.priority,
            "parallel_safe": self.is_parallel_safe,
        }


class ToolRegistry:
    """
    Central registry of all available tools.
    Brain Router queries this to decide which tools to invoke.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        logger.debug(f"[registry] Registered tool: {tool.name} ({tool.agent_name})")

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.priority)

    def list_available(self, config: dict) -> list[Tool]:
        """Return tools whose required API keys are configured."""
        available = []
        for tool in self._tools.values():
            # Always include — agents have fallback logic when keys missing
            available.append(tool)
        return sorted(available, key=lambda t: t.priority)

    def get_schemas_all(self) -> list[dict]:
        """All tool schemas for the LLM router prompt."""
        return [t.to_schema() for t in self.list_all()]

    def get_schemas(self, config: dict) -> list[dict]:
        return [t.to_schema() for t in self.list_available(config)]


def build_tool_registry(db_execute, config: dict) -> ToolRegistry:
    """
    Build and populate the full tool registry.
    Each tool is imported from its own dedicated file.
    """
    registry = ToolRegistry()

    # ── 1. Historical (priority 1 — always run, no API cost) ──
    from .historical_tool import build_historical_tool
    registry.register(build_historical_tool(db_execute, config))

    # ── 2. Memory (priority 2 — institutional learning) ───────
    from .memory_tool import build_memory_tool
    registry.register(build_memory_tool(db_execute, config))

    # ── 3. Weather (priority 2 — real-time conditions) ────────
    from .weather_tool import build_weather_tool
    registry.register(build_weather_tool(db_execute, config))

    # ── 4. News (priority 3 — disruption signals) ─────────────
    from .news_tool import build_news_tool
    registry.register(build_news_tool(db_execute, config))

    # ── 5. Port Intelligence (priority 3 — operational data) ──
    from .port_intel_tool import build_port_intel_tool
    registry.register(build_port_intel_tool(db_execute, config))

    # ── 6. Vessel Tracking (priority 4 — positional data) ─────
    from .vessel_tool import build_vessel_tool
    registry.register(build_vessel_tool(db_execute, config))

    # ── 7. Geopolitical (priority 4 — route risk) ─────────────
    from .geopolitical_tool import build_geopolitical_tool
    registry.register(build_geopolitical_tool(db_execute, config))

    logger.info(f"[registry] {len(registry._tools)} tools registered")
    return registry
