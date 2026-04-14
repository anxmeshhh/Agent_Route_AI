"""
app/agents/router.py — LLM-Based Dynamic Router

This is the BRAIN of the agentic system. Instead of a hardcoded pipeline,
the router uses Groq LLM to dynamically decide:
  1. Which agents to invoke next
  2. Whether to re-invoke an agent with different parameters
  3. Whether enough data has been collected to synthesize
  4. Which tools are most relevant for this specific query

This is what makes the system truly agentic — REASONING about next steps
instead of following a fixed script.
"""
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class AgenticRouter:
    """
    LLM-powered router that decides the next step in the analysis.
    Examines the current state and makes intelligent routing decisions.
    """

    def __init__(self, config: dict):
        self.api_key = config.get("GROQ_API_KEY", "")
        self.model = config.get("GROQ_MODEL", "llama3-8b-8192")
        self._client = None

    def _get_client(self):
        if not self._client:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def decide_next_agents(self, state: dict, available_tools: list) -> dict:
        """
        Examine current state and decide which agents to run next.

        Returns: {
            "agents_to_run": ["weather", "news", ...],
            "reasoning": "...",
            "should_synthesize": bool,
            "skip_reasons": {"agent_name": "reason"},
        }
        """
        logs = []
        logs.append(self._log("🧠 Router analyzing state — deciding next steps...", "started"))

        intake = state.get("intake", {})
        completed = state.get("completed_agents", [])
        failed = state.get("failed_agents", [])
        iteration = state.get("iteration", 0)

        # ── If this is the first iteration, use LLM routing ──
        if iteration == 0 and self.api_key and not self.api_key.startswith("your_"):
            try:
                result = self._llm_route(state, available_tools, logs)
                return result
            except Exception as e:
                logger.warning(f"[router] LLM routing failed: {e} — using rule-based")
                logs.append(self._log(f"LLM routing error: {e} — falling back to rules", "failed"))

        # ── Rule-based routing (fallback or iteration > 0) ────
        return self._rule_based_route(state, available_tools, logs)

    def _llm_route(self, state: dict, available_tools: list, logs: list) -> dict:
        """Use Groq LLM to decide which agents to invoke."""
        intake = state.get("intake", {})
        completed = state.get("completed_agents", [])

        tool_descriptions = "\n".join(
            f"  - {t['name']}: {t['description'][:100]}..."
            for t in available_tools
        )

        prompt = f"""You are the routing brain of an agentic shipment risk analysis system.

CURRENT ANALYSIS STATE:
- Query: {intake.get('query_text', state.get('query_text', 'unknown'))}
- Port: {intake.get('port', 'unknown')}
- Port City: {intake.get('port_city', 'unknown')}
- Origin: {intake.get('origin_port', 'unknown')}
- ETA: {intake.get('eta_days', 'unknown')} days
- Cargo: {intake.get('cargo_type', 'general')}
- Vessel: {intake.get('vessel_name', 'unknown')}
- Completed agents: {completed or 'none yet'}

AVAILABLE TOOLS:
{tool_descriptions}

INSTRUCTIONS:
Based on the shipment details, decide which tools to invoke. Consider:
1. Is vessel tracking useful? (Only if vessel name is known or ETA verification matters)
2. Is port intelligence useful? (Always useful if port is known)
3. Is geopolitical analysis needed? (For routes through volatile regions)
4. Should we search memory for past similar analyses?
5. Weather, news, and historical are almost always useful.

Return ONLY a JSON object (no markdown, no text outside JSON):
{{
  "agents_to_run": ["agent_name1", "agent_name2", ...],
  "reasoning": "Brief explanation of why these agents were selected",
  "skip_reasons": {{"skipped_agent": "reason for skipping"}}
}}

Valid agent names: weather, news, historical, vessel, port_intel, geopolitical, memory
"""

        t0 = time.time()
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an agentic routing brain. Respond with JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
            timeout=10.0,
        )
        duration = int((time.time() - t0) * 1000)
        raw = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens if response.usage else 0

        logs.append(self._log(
            f"LLM routing decision in {duration}ms ({tokens} tokens)",
            "success"
        ))

        # Parse JSON response
        try:
            # Try direct parse
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Extract JSON from text
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                parsed = json.loads(match.group(0))
            else:
                raise ValueError(f"Could not parse routing JSON: {raw[:200]}")

        agents = parsed.get("agents_to_run", [])
        reasoning = parsed.get("reasoning", "LLM-directed routing")
        skip_reasons = parsed.get("skip_reasons", {})

        # Validate agent names
        valid_agents = {"weather", "news", "historical", "vessel", "port_intel", "geopolitical", "memory"}
        agents = [a for a in agents if a in valid_agents]

        logs.append(self._log(
            f"Route decided: {' → '.join(agents)} | {reasoning[:80]}",
            "success"
        ))

        return {
            "agents_to_run": agents,
            "reasoning": reasoning,
            "should_synthesize": False,
            "skip_reasons": skip_reasons,
            "llm_tokens": tokens,
            "logs": logs,
        }

    def _rule_based_route(self, state: dict, available_tools: list, logs: list) -> dict:
        """
        TRULY agentic routing — makes context-aware decisions about which
        agents to run based on transport mode, geography, and data availability.

        Key agentic behaviors:
          - Domestic road routes → skip vessel, port_intel, geopolitical
          - Air freight → skip vessel tracking (no maritime data)
          - Same-country routes → skip geopolitical (no cross-border risk)
          - No vessel name → skip vessel tracking
        """
        intake = state.get("intake", {})
        completed = set(state.get("completed_agents", []))
        failed = set(state.get("failed_agents", []))
        iteration = state.get("iteration", 0)

        port = intake.get("port")
        port_city = intake.get("port_city")
        vessel = intake.get("vessel_name")
        origin = intake.get("origin_port")
        eta = intake.get("eta_days", 7)
        cargo = intake.get("cargo_type", "general")
        query = intake.get("query_text", state.get("query_text", "")).lower()

        agents_to_run = []
        skip_reasons = {}
        reasoning_parts = []

        available_names = {t["name"] for t in available_tools}

        # ══════════════════════════════════════════════════════════
        # AGENTIC INTELLIGENCE: Detect transport context
        # ══════════════════════════════════════════════════════════
        is_domestic_road = self._is_domestic_route(origin, port)
        is_air_freight = any(kw in query for kw in ["air", "flight", "cargo flight", "air freight", "airfreight", "aircraft"])
        is_maritime = any(kw in query for kw in ["sea", "maritime", "ship", "vessel", "ocean", "container ship"])
        is_international = not is_domestic_road

        # Determine transport mode for skip logic
        if is_air_freight:
            transport_context = "air"
        elif is_domestic_road:
            transport_context = "domestic_road"
        elif is_maritime or is_international:
            transport_context = "maritime"
        else:
            transport_context = "general"

        logs.append(self._log(
            f"🧠 Transport context detected: {transport_context.upper()} "
            f"| Origin: {origin or '?'} → Dest: {port or '?'} "
            f"| Domestic: {is_domestic_road} | Air: {is_air_freight}",
            "started"
        ))

        # ── Core agents (almost always useful) ─────────────────
        if "weather" not in completed and "weather" not in failed:
            if port_city or port:
                agents_to_run.append("weather")
                reasoning_parts.append("destination weather conditions")
            else:
                skip_reasons["weather"] = "no destination city resolved — cannot fetch weather"

        if "news" not in completed and "news" not in failed:
            agents_to_run.append("news")
            reasoning_parts.append("disruption signals from global news")

        if "historical" not in completed and "historical" not in failed:
            if port:
                agents_to_run.append("historical")
                reasoning_parts.append("historical delay patterns for this route")
            else:
                skip_reasons["historical"] = "no destination port — no delay history to query"

        # ── Memory recall (always useful if we have a port) ───
        if "memory" not in completed and "memory" not in failed:
            if port:
                agents_to_run.append("memory")
                reasoning_parts.append("recall past similar analyses")

        # ══════════════════════════════════════════════════════════
        # AGENTIC SKIP LOGIC: Context-aware agent filtering
        # ══════════════════════════════════════════════════════════

        # PORT INTELLIGENCE — skip for domestic road (no port involved)
        if "port_intel" not in completed and "port_intel" not in failed:
            if transport_context == "domestic_road":
                skip_reasons["port_intel"] = (
                    "Domestic road route — no seaport involved. "
                    "Port intelligence is irrelevant for land-only transport."
                )
            elif port or port_city:
                agents_to_run.append("port_intel")
                reasoning_parts.append("port congestion & operational data")
            else:
                skip_reasons["port_intel"] = "no port specified in query"

        # VESSEL TRACKING — skip for air and domestic road
        if "vessel" not in completed and "vessel" not in failed:
            if transport_context == "domestic_road":
                skip_reasons["vessel"] = (
                    "Domestic road shipment — no vessel to track. "
                    "Road transport uses trucks, not ships."
                )
            elif transport_context == "air":
                skip_reasons["vessel"] = (
                    "Air freight route — vessel tracking not applicable. "
                    "Aircraft don't appear in maritime AIS systems."
                )
            elif vessel or (origin and port and is_international):
                agents_to_run.append("vessel")
                reasoning_parts.append("vessel AIS tracking & ETA verification")
            else:
                skip_reasons["vessel"] = "no vessel name provided and route is not cross-ocean"

        # GEOPOLITICAL — skip for same-country domestic routes
        if "geopolitical" not in completed and "geopolitical" not in failed:
            if transport_context == "domestic_road":
                skip_reasons["geopolitical"] = (
                    "Domestic route — no international borders crossed. "
                    "Geopolitical risk analysis requires cross-border routing."
                )
            elif port:
                agents_to_run.append("geopolitical")
                reasoning_parts.append("geopolitical & sanctions risk assessment")
            else:
                skip_reasons["geopolitical"] = "no destination for geopolitical analysis"

        # ── Log the agentic decision clearly ──────────────────
        n_skipped = len(skip_reasons)
        est_time_saved = round(n_skipped * 1.4, 1)  # ~1.4s per agent

        logs.append(self._log(
            f"📋 Agents selected: {' → '.join(agents_to_run)} | "
            f"Agents skipped: {n_skipped} (saving ~{est_time_saved}s) | "
            f"Context: {transport_context}",
            "success"
        ))

        # ── Check if we should synthesize ─────────────────────
        should_synthesize = (
            iteration > 0 and
            len(completed) >= 3 and
            len(agents_to_run) == 0
        )

        reasoning = (
            f"[{transport_context.upper()}] "
            + (", ".join(reasoning_parts) if reasoning_parts else "All agents complete")
        )

        return {
            "agents_to_run": agents_to_run,
            "reasoning": reasoning,
            "should_synthesize": should_synthesize,
            "skip_reasons": skip_reasons,
            "transport_context": transport_context,
            "agents_skipped_count": n_skipped,
            "estimated_time_saved": est_time_saved,
            "llm_tokens": 0,
            "logs": logs,
        }

    # ── Helper: detect if origin+dest are in the same country ──
    DOMESTIC_CITIES = {
        "india": {
            "delhi", "new delhi", "mumbai", "bombay", "bangalore", "bengaluru",
            "chennai", "madras", "kolkata", "calcutta", "hyderabad", "pune",
            "ahmedabad", "jaipur", "lucknow", "nagpur", "surat", "kochi",
            "cochin", "trivandrum", "thiruvananthapuram", "kerala", "indore",
            "bhopal", "vadodara", "baroda", "patna", "bhubaneswar",
            "visakhapatnam", "vizag", "madurai", "amritsar", "chandigarh",
            "jodhpur", "agra", "varanasi", "guwahati", "raipur", "ranchi",
            "dehradun", "vijayawada", "mangalore", "mysore", "mysuru",
            "trichy", "tiruchirappalli", "nashik", "aurangabad", "ludhiana",
            "nhava sheva", "mundra", "coimbatore", "hubli", "belgaum",
            "belagavi", "surat",
        },
        "usa": {
            "new york", "los angeles", "chicago", "houston", "san francisco",
            "seattle", "miami", "atlanta", "dallas", "denver", "savannah",
            "long beach",
        },
        "china": {
            "shanghai", "beijing", "shenzhen", "guangzhou", "tianjin",
            "qingdao", "ningbo", "hong kong",
        },
    }

    def _is_domestic_route(self, origin: str, dest: str) -> bool:
        """Check if both origin and dest are in the same country."""
        if not origin or not dest:
            return False
        o_lower = origin.lower().strip()
        d_lower = dest.lower().strip()
        for country, cities in self.DOMESTIC_CITIES.items():
            o_match = any(c in o_lower or o_lower in c for c in cities)
            d_match = any(c in d_lower or d_lower in c for c in cities)
            if o_match and d_match:
                return True
        return False

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "router", "action": action, "status": status, "data": data}
