"""
app/agents/graph.py — LangGraph-Style State Graph Execution Engine

Custom state machine that provides LangGraph-compatible agentic orchestration
without requiring the langgraph package. This gives us:

  - Conditional routing (Brain LLM decides next step at each node)
  - Parallel agent execution for independent data gathering
  - State checkpointing at each node transition
  - Retry with backoff on failures
  - SSE streaming of every decision to the UI
  - Cost tracking per LLM call

The graph executes a DAG where:
  INTAKE → ROUTER → [AGENTS in parallel] → VALIDATOR → RESOLVER → SYNTHESIZER → CONFIDENCE → RESULT
"""
import json
import logging
import time
import uuid
import concurrent.futures
from datetime import datetime
from typing import Callable

from .state import ShipmentAnalysisState, create_initial_state
from .router import AgenticRouter
from .crew import SignalValidator, ConflictResolver, ConfidenceScorer, MitigationStrategist
from .memory import MemoryAgent

logger = logging.getLogger(__name__)


class AgentGraph:
    """
    LangGraph-style state graph for agentic shipment risk analysis.

    Architecture:
      1. INTAKE node: Parse query → structured shipment data
      2. ROUTE node: Brain LLM decides which agents to invoke
      3. EXECUTE node: Run selected agents (parallel when possible)
      4. VALIDATE node: Cross-check signals for conflicts
      5. RESOLVE node: Resolve conflicts via LLM reasoning
      6. SYNTHESIZE node: One batched Groq call for final risk assessment
      7. CONFIDENCE node: Score assessment quality
      8. MEMORY node: Store for future recall

    Each node streams its reasoning to the UI via SSE.
    """

    def __init__(self, session_id: str, push_event: Callable, config: dict, db_execute: Callable):
        self.session_id = session_id
        self.push_event = push_event
        self.config = config
        self.db_execute = db_execute
        self.max_retries = int(config.get("AGENT_MAX_RETRIES", 2))

        # Initialize components
        self.router = AgenticRouter(config)
        self.validator = SignalValidator()
        self.resolver = ConflictResolver(config)
        self.confidence_scorer = ConfidenceScorer()
        self.mitigation_strategist = MitigationStrategist()
        self.memory_agent = MemoryAgent(db_execute, config)

    def run(self, query_text: str, intake_result: dict, shipment_id: int) -> dict:
        """
        Execute the full agentic graph.
        Returns the final ShipmentAnalysisState as a dict.
        """
        t0 = time.time()

        # ── Initialize state ──────────────────────────────────
        state = create_initial_state(self.session_id, query_text, self.config)
        state["intake"] = intake_result
        state["shipment_id"] = shipment_id

        self._emit("agent_log", {
            "agent": "graph",
            "action": "🧠 Agentic Graph initialized — starting intelligent orchestration",
            "status": "started",
        })

        # ── Build tool registry ───────────────────────────────
        from ..tools.registry import build_tool_registry
        registry = build_tool_registry(self.db_execute, self.config)
        tool_schemas = registry.get_schemas_all()

        self._emit("agent_log", {
            "agent": "graph",
            "action": f"📦 {len(tool_schemas)} tools registered — Router will decide which to invoke",
            "status": "success",
        })

        # ══════════════════════════════════════════════════════
        # NODE 1: ROUTE — Brain decides which agents to run
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "router",
            "action": "🧠 Analyzing query context — deciding optimal agent sequence...",
            "status": "started",
        })

        route_result = self.router.decide_next_agents(state, tool_schemas)
        self._stream_logs(route_result.get("logs", []))

        agents_to_run = route_result.get("agents_to_run", [])
        skip_reasons = route_result.get("skip_reasons", {})

        state["pending_agents"] = agents_to_run
        state["skipped_agents"] = list(skip_reasons.keys())
        state["iteration"] = 1

        # Track LLM tokens from routing
        route_tokens = route_result.get("llm_tokens", 0)
        if route_tokens:
            state["llm_calls_made"] = state.get("llm_calls_made", 0) + 1
            state["total_tokens_used"] = state.get("total_tokens_used", 0) + route_tokens

        self._emit("agent_log", {
            "agent": "router",
            "action": f"📋 Plan: {' → '.join(agents_to_run)} | Reasoning: {route_result.get('reasoning', '')[:100]}",
            "status": "success",
        })

        for agent_name, reason in skip_reasons.items():
            self._emit("agent_log", {
                "agent": "router",
                "action": f"⏭ Skipping {agent_name}: {reason}",
                "status": "skipped",
            })

        time.sleep(0.2)

        # ══════════════════════════════════════════════════════
        # NODE 2: EXECUTE — Run agents (parallel where possible)
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "graph",
            "action": f"⚡ Executing {len(agents_to_run)} agents...",
            "status": "started",
        })

        # Separate into parallel-safe and sequential groups
        parallel_agents = []
        sequential_agents = []

        for agent_name in agents_to_run:
            tool = registry.get(self._agent_to_tool(agent_name))
            if tool and tool.is_parallel_safe:
                parallel_agents.append(agent_name)
            else:
                sequential_agents.append(agent_name)

        # Execute parallel agents
        if parallel_agents:
            self._emit("agent_log", {
                "agent": "graph",
                "action": f"🔀 Parallel execution: {', '.join(parallel_agents)}",
                "status": "started",
            })
            self._execute_agents_parallel(state, parallel_agents, registry)

        # Execute sequential agents
        for agent_name in sequential_agents:
            self._execute_single_agent(state, agent_name, registry)

        time.sleep(0.2)

        # ══════════════════════════════════════════════════════
        # NODE 3: VALIDATE — Cross-check signals
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "validator",
            "action": "🔍 Cross-validating signals from all agents...",
            "status": "started",
        })

        validation_result = self.validator.validate(state)
        self._stream_logs(validation_result.get("logs", []))
        state["conflicts"] = validation_result.get("conflicts", [])

        # ══════════════════════════════════════════════════════
        # NODE 4: RESOLVE — Handle conflicts
        # ══════════════════════════════════════════════════════
        if state["conflicts"]:
            self._emit("agent_log", {
                "agent": "resolver",
                "action": f"⚖ Resolving {len(state['conflicts'])} signal conflict(s)...",
                "status": "started",
            })
            resolve_result = self.resolver.resolve(state["conflicts"], state)
            self._stream_logs(resolve_result.get("logs", []))

        time.sleep(0.1)

        # ══════════════════════════════════════════════════════
        # NODE 5: SYNTHESIZE — One batched Groq LLM call
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "brain",
            "action": "🤖 All data gathered — initiating Groq LLM synthesis...",
            "status": "started",
        })

        from .risk_agent import RiskAgent
        risk_agent = RiskAgent(self.config)

        # Build enriched context with all agent data
        context = {
            "shipment": intake_result,
            "weather": state.get("weather"),
            "news": state.get("news"),
            "historical": state.get("historical"),
            "vessel": state.get("vessel"),
            "port_intel": state.get("port_intel"),
            "geopolitical": state.get("geopolitical"),
            "memory_recalls": state.get("memory_recalls", []),
            "conflicts": state.get("conflicts", []),
        }

        def risk_log_cb(agent, action, status):
            self._emit("agent_log", {"agent": agent, "action": action, "status": status})
            self._log_db(agent, action, status)
            time.sleep(0.08)

        final_result = risk_agent.run(context, risk_log_cb)

        # Update state with results
        state["risk_score"] = final_result.get("risk_score")
        state["risk_level"] = final_result.get("risk_level")
        state["delay_probability"] = final_result.get("delay_probability")
        state["factors"] = final_result.get("factors", [])
        state["llm_reasoning"] = final_result.get("llm_reasoning")
        state["weather_score"] = final_result.get("weather_score")
        state["news_score"] = final_result.get("news_score")
        state["historical_score"] = final_result.get("historical_score")

        if final_result.get("llm_tokens_used"):
            state["llm_calls_made"] = state.get("llm_calls_made", 0) + 1
            state["total_tokens_used"] = state.get("total_tokens_used", 0) + final_result.get("llm_tokens_used", 0)

        state["llm_model"] = final_result.get("llm_model", "unknown")

        # ══════════════════════════════════════════════════════
        # NODE 6: MITIGATION — Context-specific strategies
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "brain",
            "action": "📋 Generating context-specific mitigation strategies...",
            "status": "started",
        })

        mitigation = self.mitigation_strategist.generate(state)
        state["mitigation"] = mitigation
        final_result["mitigation"] = mitigation

        self._emit("agent_log", {
            "agent": "brain",
            "action": f"Generated {len(mitigation)} targeted mitigation strategies",
            "status": "success",
        })

        # ══════════════════════════════════════════════════════
        # NODE 7: CONFIDENCE — Score assessment quality
        # ══════════════════════════════════════════════════════
        self._emit("agent_log", {
            "agent": "confidence",
            "action": "📊 Computing assessment confidence score...",
            "status": "started",
        })

        confidence_result = self.confidence_scorer.score(state, validation_result)
        self._stream_logs(confidence_result.get("logs", []))

        state["confidence_score"] = confidence_result["confidence_score"]
        state["confidence_breakdown"] = confidence_result["confidence_breakdown"]
        state["needs_human_review"] = confidence_result["needs_human_review"]

        # ══════════════════════════════════════════════════════
        # NODE 8: MEMORY — Store for future recall
        # ══════════════════════════════════════════════════════
        try:
            self.memory_agent.store(
                self.session_id,
                intake_result.get("port"),
                intake_result.get("cargo_type"),
                state.get("risk_score"),
                state.get("risk_level"),
                state.get("factors", []),
            )
            self._emit("agent_log", {
                "agent": "memory",
                "action": "💾 Analysis stored in memory for future recall",
                "status": "success",
            })
        except Exception as e:
            logger.warning(f"[graph] Memory store error: {e}")

        # ── Persist risk assessment to MySQL ──────────────────
        self._emit("agent_log", {
            "agent": "brain",
            "action": f"Persisting risk assessment — score: {state.get('risk_score')}/100",
            "status": "started",
        })

        try:
            self._save_assessment(shipment_id, final_result)
            self._emit("agent_log", {
                "agent": "brain",
                "action": "✅ Risk assessment saved to MySQL",
                "status": "success",
            })
        except Exception as e:
            logger.error(f"[graph] Save error: {e}")
            self._emit("agent_log", {
                "agent": "brain",
                "action": f"DB save warning: {e}",
                "status": "failed",
            })

        # ── Finalize ──────────────────────────────────────────
        total_duration = int((time.time() - t0) * 1000)
        state["total_duration_ms"] = total_duration
        state["status"] = "completed"

        # Build final output
        final_result["intake"] = intake_result
        final_result["session_id"] = self.session_id
        # Propagate dynamic ETA fields to top level for frontend
        final_result["eta_days"] = intake_result.get("eta_days")
        final_result["eta_hours"] = intake_result.get("eta_hours")
        final_result["eta_source"] = intake_result.get("eta_source")
        # Propagate transport mode + calibrated risk fields
        final_result["transport_mode"] = final_result.get("transport_mode") or intake_result.get("transport_mode")
        final_result["risk_probability"] = final_result.get("risk_probability")
        final_result["risk_explanation"] = final_result.get("risk_explanation")
        final_result["decision_synthesis"] = final_result.get("decision_synthesis")
        final_result["trade_offs"] = final_result.get("trade_offs")
        final_result["confidence_score"] = state["confidence_score"]
        final_result["confidence_breakdown"] = state["confidence_breakdown"]
        final_result["needs_human_review"] = state["needs_human_review"]
        final_result["completed_agents"] = state.get("completed_agents", [])
        final_result["skipped_agents"] = state.get("skipped_agents", [])
        final_result["failed_agents"] = state.get("failed_agents", [])
        final_result["conflicts"] = state.get("conflicts", [])
        final_result["memory_recalls"] = state.get("memory_recalls", [])
        final_result["llm_calls_made"] = state.get("llm_calls_made", 0)
        final_result["total_tokens_used"] = state.get("total_tokens_used", 0)
        final_result["total_duration_ms"] = total_duration
        final_result["tool_calls"] = state.get("tool_calls", [])

        # Attach extended agent data for UI
        final_result["vessel_data"] = state.get("vessel")
        final_result["port_intel_data"] = state.get("port_intel")
        final_result["geopolitical_data"] = state.get("geopolitical")
        final_result["news"] = state.get("news")
        final_result["weather"] = state.get("weather")
        final_result["historical"] = state.get("historical")

        self._emit("agent_log", {
            "agent": "graph",
            "action": (
                f"✅ Analysis complete — Risk: {state.get('risk_level')} "
                f"({state.get('risk_score')}/100) | "
                f"Confidence: {state['confidence_score']:.0%} | "
                f"{state.get('llm_calls_made', 0)} LLM calls | "
                f"{total_duration}ms total"
            ),
            "status": "success",
        })

        self._log_db("graph", "Analysis pipeline complete", "success", {
            "risk_score": state.get("risk_score"),
            "risk_level": state.get("risk_level"),
            "confidence": state["confidence_score"],
            "duration_ms": total_duration,
            "agents_completed": state.get("completed_agents"),
        })

        return final_result

    # ─── Agent execution ─────────────────────────────────────
    def _execute_agents_parallel(self, state: dict, agent_names: list, registry):
        """Execute multiple independent agents in parallel."""
        from flask import current_app
        app = current_app._get_current_object()

        def worker(name):
            with app.app_context():
                return self._execute_single_agent_internal(state, name, registry)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for name in agent_names:
                future = executor.submit(worker, name)
                futures[future] = name

            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if result:
                        state[name] = result
                        self._collect_signals(state, name, result)
                        state.setdefault("completed_agents", []).append(name)
                except Exception as e:
                    logger.error(f"[graph] Parallel agent {name} error: {e}")
                    state.setdefault("failed_agents", []).append(name)

    def _execute_single_agent(self, state: dict, agent_name: str, registry):
        """Execute a single agent with retry logic and SSE streaming."""
        result = self._execute_single_agent_internal(state, agent_name, registry)
        if result:
            state[agent_name] = result
            self._collect_signals(state, agent_name, result)
            state.setdefault("completed_agents", []).append(agent_name)
        else:
            state.setdefault("failed_agents", []).append(agent_name)

    def _execute_single_agent_internal(self, state: dict, agent_name: str, registry):
        """Internal agent execution with retry."""
        intake = state.get("intake", {})

        for attempt in range(1, self.max_retries + 2):
            try:
                if attempt > 1:
                    self._emit("agent_log", {
                        "agent": "graph",
                        "action": f"↻ Retrying {agent_name} agent (attempt {attempt})",
                        "status": "retrying",
                    })
                    time.sleep(1.0)

                result = self._dispatch_agent(agent_name, intake, state)

                # Stream agent logs to UI
                for log in result.get("logs", []):
                    self._emit("agent_log", {
                        "agent": log.get("agent", agent_name),
                        "action": log.get("action", ""),
                        "status": log.get("status", "success"),
                    })
                    self._log_db(
                        log.get("agent", agent_name),
                        log.get("action", ""),
                        log.get("status", "success"),
                        log.get("data"),
                    )
                    time.sleep(0.06)

                # Record tool call
                state.setdefault("tool_calls", []).append({
                    "tool_name": self._agent_to_tool(agent_name),
                    "agent": agent_name,
                    "duration_ms": 0,
                    "cache_hit": result.get("source") == "cache",
                    "timestamp": datetime.utcnow().isoformat(),
                })

                return result

            except Exception as e:
                logger.warning(f"[graph] {agent_name} attempt {attempt} failed: {e}")
                self._emit("agent_log", {
                    "agent": agent_name,
                    "action": f"Agent error (attempt {attempt}): {str(e)[:80]}",
                    "status": "failed",
                })
                if attempt > self.max_retries:
                    self._emit("agent_log", {
                        "agent": "graph",
                        "action": f"⚠ {agent_name} exhausted retries — continuing without it",
                        "status": "skipped",
                    })
                    return None

        return None

    def _dispatch_agent(self, name: str, intake: dict, state: dict) -> dict:
        """Instantiate and run the correct agent."""
        port = intake.get("port")
        port_city = intake.get("port_city") or port
        eta_days = intake.get("eta_days", 7)
        cargo = intake.get("cargo_type", "general")
        vessel = intake.get("vessel_name")
        origin = intake.get("origin_port")
        sid = self.session_id

        if name == "weather":
            from .weather_agent import WeatherAgent
            agent = WeatherAgent(self.db_execute, self.config)
            return agent.run(port_city or port, sid)

        elif name == "news":
            from .news_agent import NewsAgent
            agent = NewsAgent(self.db_execute, self.config)
            return agent.run(port, port_city, sid)

        elif name == "historical":
            from .historical_agent import HistoricalAgent
            agent = HistoricalAgent(self.db_execute, self.config)
            return agent.run(port, eta_days, cargo, sid)

        elif name == "vessel":
            from .vessel_agent import VesselAgent
            agent = VesselAgent(self.db_execute, self.config)
            return agent.run(vessel, origin, port, eta_days, sid)

        elif name == "port_intel":
            from .port_intel_agent import PortIntelAgent
            agent = PortIntelAgent(self.db_execute, self.config)
            return agent.run(port, port_city, sid)

        elif name == "geopolitical":
            from .geopolitical_agent import GeopoliticalAgent
            agent = GeopoliticalAgent(self.db_execute, self.config)
            return agent.run(port, origin, None, sid)

        elif name == "memory":
            result = self.memory_agent.recall(port, cargo, sid)
            state["memory_recalls"] = result.get("similar_analyses", [])
            return result

        raise ValueError(f"Unknown agent: {name}")

    def _collect_signals(self, state: dict, agent_name: str, result: dict):
        """Collect risk signals from an agent's output into the shared state."""
        signals = result.get("risk_signals", [])
        for signal in signals:
            signal["source_agent"] = agent_name
            state.setdefault("signals", []).append(signal)

    def _agent_to_tool(self, agent_name: str) -> str:
        """Map agent name to tool name."""
        mapping = {
            "weather": "fetch_weather",
            "news": "search_news",
            "historical": "query_historical",
            "vessel": "track_vessel",
            "port_intel": "get_port_intel",
            "geopolitical": "assess_geopolitical",
            "memory": "search_memory",
        }
        return mapping.get(agent_name, agent_name)

    # ─── Persistence ─────────────────────────────────────────
    def _save_assessment(self, shipment_id: int, result: dict):
        self.db_execute(
            """INSERT INTO risk_assessments
                (shipment_id, session_id, risk_score, risk_level, delay_probability,
                 weather_score, news_score, historical_score,
                 factors_json, mitigation_json, llm_reasoning, llm_model, llm_tokens_used,
                 confidence_score)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 risk_score=VALUES(risk_score), risk_level=VALUES(risk_level),
                 delay_probability=VALUES(delay_probability),
                 factors_json=VALUES(factors_json), mitigation_json=VALUES(mitigation_json),
                 llm_reasoning=VALUES(llm_reasoning), confidence_score=VALUES(confidence_score)""",
            (
                shipment_id, self.session_id,
                result.get("risk_score"), result.get("risk_level"),
                result.get("delay_probability"),
                result.get("weather_score"), result.get("news_score"),
                result.get("historical_score"),
                json.dumps(result.get("factors", [])),
                json.dumps(result.get("mitigation", [])),
                result.get("llm_reasoning"),
                result.get("llm_model", "unknown"),
                result.get("llm_tokens_used", 0),
                result.get("confidence_score", 0),
            ),
        )

    def _log_db(self, agent: str, action: str, status: str, data: dict = None):
        try:
            self.db_execute(
                """INSERT INTO agent_logs (session_id, agent_name, action, status, data_json)
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.session_id, agent, action[:255], status,
                 self._safe_json(data) if data else None),
            )
        except Exception as e:
            logger.debug(f"[graph] Log DB error: {e}")

    @staticmethod
    def _safe_json(obj) -> str:
        """JSON-serialize any object, converting Decimal, datetime, etc. safely."""
        import decimal
        from datetime import date

        def default(o):
            if isinstance(o, decimal.Decimal):
                return float(o)
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            return str(o)

        return json.dumps(obj, default=default)

    def _stream_logs(self, logs: list):
        """Stream a batch of logs to the UI."""
        for log in logs:
            self._emit("agent_log", {
                "agent": log.get("agent", "system"),
                "action": log.get("action", ""),
                "status": log.get("status", "success"),
            })
            self._log_db(
                log.get("agent", "system"),
                log.get("action", ""),
                log.get("status", "success"),
                log.get("data"),
            )
            time.sleep(0.06)

    def _emit(self, event_type: str, data: dict):
        """Push SSE event to the UI."""
        self.push_event(self.session_id, event_type, data)
        time.sleep(0.04)
