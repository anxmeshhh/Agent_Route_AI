"""
app/agents/state.py — Agentic State Definition

The shared state object that flows through the entire graph.
Every agent reads from and writes to this state.
This is the backbone of truly agentic behaviour — agents can see
what other agents have done, what the Brain is thinking, and adapt.
"""
from typing import TypedDict, Optional, Any


class ReasoningStep(TypedDict, total=False):
    """A single step in the reasoning chain — full transparency."""
    agent: str
    thought: str          # What the agent is thinking
    action: str           # What it decided to do
    observation: str      # What it observed after the action
    status: str           # success / failed / skipped / retrying
    data: Optional[dict]  # Structured output
    duration_ms: int
    timestamp: str


class AgentSignal(TypedDict, total=False):
    """A risk signal produced by any agent."""
    source_agent: str
    type: str             # weather / news / historical / vessel / port / geopolitical
    title: str
    detail: str
    severity: str         # LOW / MEDIUM / HIGH / CRITICAL
    confidence: float     # 0.0 - 1.0
    raw_data: Optional[dict]


class ToolCall(TypedDict, total=False):
    """Record of a tool invocation."""
    tool_name: str
    agent: str
    input_params: dict
    output_summary: str
    duration_ms: int
    cost_estimate: float  # estimated API cost
    cache_hit: bool
    timestamp: str


class ShipmentAnalysisState(TypedDict, total=False):
    """
    The complete state for one analysis run.
    Flows through the LangGraph-style state machine.
    Every node (agent) reads and modifies this.
    """
    # ── Identity ──────────────────────────────────────────────
    session_id: str
    shipment_id: Optional[int]

    # ── Input ─────────────────────────────────────────────────
    query_text: str
    intake: Optional[dict]          # Parsed shipment data

    # ── Agent outputs ─────────────────────────────────────────
    weather: Optional[dict]
    news: Optional[dict]
    historical: Optional[dict]
    vessel: Optional[dict]
    port_intel: Optional[dict]
    geopolitical: Optional[dict]

    # ── Agentic reasoning ─────────────────────────────────────
    reasoning_chain: list            # List[ReasoningStep] — full thought trace
    signals: list                    # List[AgentSignal] — all collected signals
    tool_calls: list                 # List[ToolCall] — all tool invocations
    conflicts: list                  # Signal conflicts detected by validator
    memory_recalls: list             # Past analyses recalled by memory agent

    # ── Routing & control flow ────────────────────────────────
    pending_agents: list             # Agents the router wants to invoke next
    completed_agents: list           # Agents that have finished
    failed_agents: list              # Agents that failed all retries
    skipped_agents: list             # Agents the router decided to skip
    iteration: int                   # How many routing loops we've done
    max_iterations: int              # Safety limit (default 5)

    # ── Confidence & quality ──────────────────────────────────
    confidence_score: float          # 0.0 - 1.0, overall confidence
    confidence_breakdown: dict       # Per-dimension confidence
    data_freshness: dict             # How fresh each data source is
    needs_human_review: bool         # Whether confidence is too low

    # ── Final output ──────────────────────────────────────────
    risk_score: Optional[int]        # 0-100
    risk_level: Optional[str]        # LOW / MEDIUM / HIGH / CRITICAL
    delay_probability: Optional[float]
    factors: list                    # Final prioritised risk factors
    mitigation: list                 # Final mitigation strategies
    llm_reasoning: Optional[str]     # Narrative summary
    weather_score: Optional[int]
    news_score: Optional[int]
    historical_score: Optional[int]

    # ── Metadata ──────────────────────────────────────────────
    llm_calls_made: int
    total_tokens_used: int
    total_duration_ms: int
    llm_model: str
    status: str                      # running / completed / failed / needs_review


def create_initial_state(session_id: str, query_text: str, config: dict) -> ShipmentAnalysisState:
    """Create a fresh state for a new analysis run."""
    return ShipmentAnalysisState(
        session_id=session_id,
        shipment_id=None,
        query_text=query_text,
        intake=None,
        weather=None,
        news=None,
        historical=None,
        vessel=None,
        port_intel=None,
        geopolitical=None,
        reasoning_chain=[],
        signals=[],
        tool_calls=[],
        conflicts=[],
        memory_recalls=[],
        pending_agents=[],
        completed_agents=[],
        failed_agents=[],
        skipped_agents=[],
        iteration=0,
        max_iterations=int(config.get("MAX_GRAPH_ITERATIONS", 5)),
        confidence_score=0.0,
        confidence_breakdown={},
        data_freshness={},
        needs_human_review=False,
        risk_score=None,
        risk_level=None,
        delay_probability=None,
        factors=[],
        mitigation=[],
        llm_reasoning=None,
        weather_score=None,
        news_score=None,
        historical_score=None,
        llm_calls_made=0,
        total_tokens_used=0,
        total_duration_ms=0,
        llm_model=config.get("GROQ_MODEL", "llama3-8b-8192"),
        status="running",
    )
