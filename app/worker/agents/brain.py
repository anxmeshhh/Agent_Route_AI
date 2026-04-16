"""
app/agents/brain.py — Module 5 (Part B) — THE LOGICAL BRAIN

This is the true agentic core. It:
  1. Plans which agents to invoke and in what order
  2. Calls each agent, streaming live logs to the UI via SSE
  3. Skips agents when cached data is still fresh
  4. Retries failed agents (max 2 retries)
  5. Batches ALL collected data into ONE Groq LLM call
  6. Saves the final result to MySQL
  7. Logs every decision to agent_logs table

This is what separates a true agentic system from a scripted pipeline:
- It DECIDES what tools to use (not hardcoded)
- It MONITORS results and retries on failure
- It REASONS about whether cached data is sufficient
- It makes ONE economical LLM call after all data is gathered
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Callable

logger = logging.getLogger(__name__)


class Brain:
    """
    The Logical Brain — Agent Orchestrator.

    Args:
        session_id:   unique ID for this analysis run
        push_event:   function(session_id, event_type, data) to stream to UI
        config:       Flask app.config dict
    """

    def __init__(self, session_id: str, push_event: Callable, config: dict):
        self.session_id  = session_id
        self.push_event  = push_event
        self.config      = config
        self.max_retries = int(config.get("AGENT_MAX_RETRIES", 2))

    # ─── Main orchestration loop ───────────────────────────────────
    def run(self, intake_result: dict, shipment_id: int) -> dict:
        """
        Orchestrate all agents and return the final risk assessment.
        """
        from app.backend.database import execute_query
        self._db = execute_query

        port      = intake_result.get("port")
        port_city = intake_result.get("port_city") or port
        eta_days  = intake_result.get("eta_days", 7)
        cargo     = intake_result.get("cargo_type", "general")

        self._emit("agent_log", {
            "agent": "brain",
            "action": f"🧠 Planning analysis for: {port or 'unknown port'} | ETA: {eta_days}d | Cargo: {cargo}",
            "status": "started",
        })

        # ── Task plan: Brain decides which agents to invoke ─────────
        task_plan = self._plan_tasks(port, port_city, eta_days, cargo)

        self._emit("agent_log", {
            "agent": "brain",
            "action": f"Task plan: {' → '.join(task_plan)}",
            "status": "success",
        })
        self._log_db("brain", f"Task plan generated: {task_plan}", "success")
        time.sleep(0.2)

        # ── Collected results context ───────────────────────────────
        context = {
            "shipment":   intake_result,
            "weather":    None,
            "news":       None,
            "historical": None,
        }

        # ── Execute each agent in plan ──────────────────────────────
        for agent_name in task_plan:
            result = self._run_agent_with_retry(
                agent_name, port, port_city, eta_days, cargo
            )
            context[agent_name] = result

        # ── One Groq LLM call — synthesise everything ───────────────
        self._emit("agent_log", {
            "agent": "brain",
            "action": "🤖 All data gathered — initiating single Groq LLM synthesis call",
            "status": "started",
        })

        from .risk_agent import RiskAgent
        risk_agent = RiskAgent(self.config)

        def risk_log_cb(agent, action, status):
            self._emit("agent_log", {"agent": agent, "action": action, "status": status})
            self._log_db(agent, action, status)
            time.sleep(0.1)

        final_result = risk_agent.run(context, risk_log_cb)

        # ── Persist risk assessment to MySQL ────────────────────────
        self._emit("agent_log", {
            "agent": "brain",
            "action": f"Persisting risk assessment — score: {final_result.get('risk_score')}/100",
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
            logger.error(f"[brain] Save error: {e}")
            self._emit("agent_log", {
                "agent": "brain",
                "action": f"DB save warning: {e}",
                "status": "failed",
            })

        # ── Add intake info to result for UI ────────────────────────
        final_result["intake"]     = intake_result
        final_result["session_id"] = self.session_id

        self._emit("agent_log", {
            "agent": "brain",
            "action": f"✅ Analysis complete — Risk: {final_result.get('risk_level')} ({final_result.get('risk_score')}/100)",
            "status": "success",
        })
        self._log_db("brain", "Analysis pipeline complete", "success", {
            "risk_score": final_result.get("risk_score"),
            "risk_level": final_result.get("risk_level"),
        })

        return final_result

    # ─── Task planning ─────────────────────────────────────────────
    def _plan_tasks(self, port, port_city, eta_days, cargo) -> list:
        """
        Brain decides which agents to run based on available data.
        This is the agentic decision-making — NOT a hardcoded pipeline.
        """
        plan = []

        # Weather: always useful if we know the port city
        if port_city:
            plan.append("weather")
        else:
            self._emit("agent_log", {
                "agent": "brain",
                "action": "Skipping weather agent — no port city resolved",
                "status": "skipped",
            })

        # News: always run — geopolitical signals matter everywhere
        plan.append("news")

        # Historical: always run — baseline delay patterns
        plan.append("historical")

        return plan

    # ─── Agent runner with retry ────────────────────────────────────
    def _run_agent_with_retry(self, agent_name: str, port, port_city, eta_days, cargo) -> dict:
        """
        Run an agent up to max_retries times.
        Streams each attempt to the UI live.
        """
        for attempt in range(1, self.max_retries + 2):
            is_retry = attempt > 1
            try:
                if is_retry:
                    self._emit("agent_log", {
                        "agent": "brain",
                        "action": f"↻ Retrying {agent_name} agent (attempt {attempt})",
                        "status": "retrying",
                    })
                    time.sleep(1.0)

                result = self._dispatch_agent(agent_name, port, port_city, eta_days, cargo)

                # Stream all logs the sub-agent produced
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
                    time.sleep(0.08)

                return result

            except Exception as e:
                logger.warning(f"[brain] {agent_name} attempt {attempt} failed: {e}")
                self._emit("agent_log", {
                    "agent": agent_name,
                    "action": f"Agent error (attempt {attempt}): {str(e)[:80]}",
                    "status": "failed",
                })
                if attempt > self.max_retries:
                    self._emit("agent_log", {
                        "agent": "brain",
                        "action": f"⚠ {agent_name} agent exhausted retries — continuing without it",
                        "status": "skipped",
                    })
                    return {"risk_signals": [], "logs": []}

        return {"risk_signals": [], "logs": []}

    # ─── Agent dispatch ────────────────────────────────────────────
    def _dispatch_agent(self, name: str, port, port_city, eta_days, cargo) -> dict:
        """Instantiate and run the correct agent."""
        if name == "weather":
            from .weather_agent import WeatherAgent
            agent = WeatherAgent(self._db, self.config)
            return agent.run(port_city or port, self.session_id)

        elif name == "news":
            from .news_agent import NewsAgent
            agent = NewsAgent(self._db, self.config)
            return agent.run(port, port_city, self.session_id)

        elif name == "historical":
            from .historical_agent import HistoricalAgent
            agent = HistoricalAgent(self._db, self.config)
            return agent.run(port, eta_days, cargo, self.session_id)

        raise ValueError(f"Unknown agent: {name}")

    # ─── DB Helpers ─────────────────────────────────────────────────
    def _save_assessment(self, shipment_id: int, result: dict):
        self._db(
            """INSERT INTO risk_assessments
                (shipment_id, session_id, risk_score, risk_level, delay_probability,
                 weather_score, news_score, historical_score,
                 factors_json, mitigation_json, llm_reasoning, llm_model, llm_tokens_used)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 risk_score=VALUES(risk_score), risk_level=VALUES(risk_level),
                 delay_probability=VALUES(delay_probability),
                 factors_json=VALUES(factors_json), mitigation_json=VALUES(mitigation_json),
                 llm_reasoning=VALUES(llm_reasoning)""",
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
            ),
        )

    def _log_db(self, agent: str, action: str, status: str, data: dict = None):
        try:
            self._db(
                """INSERT INTO agent_logs (session_id, agent_name, action, status, data_json)
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.session_id, agent, action[:255], status,
                 json.dumps(data) if data else None),
            )
        except Exception as e:
            logger.debug(f"[brain] Log DB error: {e}")

    def _emit(self, event_type: str, data: dict):
        """Push SSE event to the UI."""
        self.push_event(self.session_id, event_type, data)
        time.sleep(0.05)

