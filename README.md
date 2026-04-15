# 🗺 AgentRouteAI — AI Decision Intelligence System

> **8-agent autonomous AI platform** that goes beyond prediction — transforming raw shipment queries into risk-assessed, scenario-simulated, explainable, and optimized routing decisions in real-time.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama3-orange)
![License](https://img.shields.io/badge/License-MIT-green)
![Multi-Agent](https://img.shields.io/badge/System-Multi--Agent-blueviolet)
![XAI](https://img.shields.io/badge/Explainability-XAI%20Enabled-brightgreen)

---

## Problem Statement

Global supply chain managers face **$1.6 trillion in annual losses** from shipment delays, unpredictable weather, port congestion, and geopolitical disruptions. Existing tools provide static ETAs without understanding the *why* behind delays or offering intelligent alternatives.

**AgentRouteAI** solves this with an **AI Decision Intelligence System** — a structured, multi-agent autonomous platform that:
- Identifies and scores every possible risk
- Simulates Best / Most Likely / Worst case futures
- Debates decisions across specialized agents before committing
- Explains every decision with percentages and causal reasoning (XAI)
- Adapts in real-time to changing constraints

---

## 🔷 Core Objective

Transform any raw shipment query into:

| Output | Description |
|---|---|
| 🔍 **Risk Analysis** | Probability-scored risk registry with critical threat highlighting |
| 🤖 **Agent Insights** | Independent perspectives from Risk, Cost, and Operations agents |
| ⚔️ **Agent Debate** | Cross-agent disagreements resolved via structured debate |
| 🔮 **Scenario Simulation** | Best / Most Likely / Worst case projections with impact metrics |
| ✅ **Final Decision** | Optimal route + mitigation strategy output |
| 🚀 **Recommended Actions** | Top 2–3 specific, executable actions |
| 📊 **Confidence Score** | Decision confidence from 0.0 → 1.0 |
| 🧠 **XAI Explanation** | Top contributing factors with percentage weights |
| 🔁 **What-If Analysis** | How the decision shifts under alternate budget/time constraints |
| 🧬 **Memory Insight** | Reference to similar past cases and their outcomes |

---

## 🔷 System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Flask Web Server                          │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────────────┐   │
│  │Dashboard │   │ SSE Streaming │   │   REST API Layer     │   │
│  └────┬─────┘   └───────┬───────┘   └──────────┬───────────┘   │
│       └─────────────────┼───────────────────────┘               │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │  Decision Intelligence│ ← Core Orchestrator      │
│              │       Engine         │   (LangGraph-style FSM)   │
│              └──────────┬───────────┘                           │
│          ┌──────────────┼──────────────┐                        │
│          ▼              ▼              ▼                         │
│   ┌────────────┐ ┌────────────┐ ┌────────────┐                 │
│   │ Risk       │ │ Cost       │ │ Operations │                  │
│   │ Analyst    │ │ Optimization│ │ Agent      │                  │
│   │ Agent      │ │ Agent      │ │            │                  │
│   └─────┬──────┘ └─────┬──────┘ └──────┬─────┘                 │
│         └──────────────┼───────────────┘                        │
│                        ▼                                         │
│              ┌──────────────────────┐                           │
│              │   Agent Debate Phase │ ← Conflict Resolution     │
│              └──────────┬───────────┘                           │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │  Scenario Simulation │ ← Best/Likely/Worst       │
│              │       Engine         │                            │
│              └──────────┬───────────┘                           │
│                         ▼                                        │
│   ┌─────────┬───────────┴───────────┬──────────────────────┐   │
│   │  XAI    │  Memory Simulation    │  Real-Time Adapter   │   │
│   │ Engine  │  (Past Case Recall)   │  (What-If Engine)    │   │
│   └─────────┴───────────────────────┴──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │ Specialized Data Agents│
              │  Weather │ News │ AIS  │
              │  Port    │ Geo  │ Hist │
              └───────────────────────┘
                          │
              ┌───────────┴───────────┐
              │   MySQL (InnoDB)      │
              │   7 tables            │
              └───────────────────────┘
```

---

## 🔷 Multi-Agent System (To Be Implemented)

The system must simulate **three strategic decision-making agents** in addition to the existing eight data-gathering agents. These agents operate in parallel, then enter a structured debate phase before the Decision Engine synthesizes results.

---

### Agent 1 — Risk Analyst Agent

**Role:** Identify, score, and prioritize all risks associated with the current shipment query.

**What it must do:**
- Enumerate all possible risk categories:
  - Weather / Natural Disaster
  - Geopolitical / Sanctions
  - Port Congestion
  - Regulatory / Customs
  - Cargo Sensitivity (perishable, hazardous)
  - Carrier/Vessel failure
  - Market price volatility
- Assign a **probability score (0–100%)** to each risk
- Flag a risk as **CRITICAL** if it exceeds 65% probability
- Output a ranked risk registry sorted by severity × probability

**Output schema (per risk item):**
```json
{
  "risk_id": "R-001",
  "category": "Geopolitical",
  "description": "Red Sea transit disruption from Houthi activity",
  "probability": 82,
  "severity": "CRITICAL",
  "impact_days": 7,
  "impact_cost_usd": 35000
}
```

**Implementation location:** `app/agents/risk_analyst_agent.py` *(to be created)*

---

### Agent 2 — Cost Optimization Agent

**Role:** Evaluate the full financial impact of each routing option and recommend cost-efficient alternatives.

**What it must do:**
- Calculate total cost for each route variation:
  - Fuel cost (distance × fuel rate)
  - Port fees and tariffs
  - Delay penalties (contractual SLA cost-per-day)
  - Insurance premium adjustments based on risk score
  - Alternate route surcharges (e.g., Cape of Good Hope detour adds ~12 days + $45,000 fuel)
- Perform explicit **trade-off analysis** (cost vs. speed vs. risk)
- Flag if the cheapest option carries a hidden risk premium > 30%

**Output schema:**
```json
{
  "route": "Suez Canal",
  "estimated_cost_usd": 120000,
  "risk_adjusted_cost_usd": 167000,
  "eta_days": 28,
  "cost_per_day": 4285,
  "recommendation": "Not cost-optimal due to 82% geopolitical disruption probability"
}
```

**Implementation location:** `app/agents/cost_optimization_agent.py` *(to be created)*

---

### Agent 3 — Operations Agent

**Role:** Assess real-world execution feasibility and propose concrete execution strategies.

**What it must do:**
- Validate that the proposed route is currently operationally viable:
  - Port open / not under strike action
  - Vessel capacity and availability
  - Customs clearance timelines at origin/destination
  - Regulatory compliance (ISPS code, SOLAS)
- Identify hard constraints (e.g., vessel cannot exceed draft at destination port)
- Propose execution sequence with milestones:
  1. Origin departure window
  2. Waypoint ETAs
  3. Pre-clearance triggers
  4. Contingency checkpoints

**Output schema:**
```json
{
  "feasibility": "HIGH",
  "blockers": [],
  "execution_plan": [
    { "milestone": "Depart Shanghai", "eta": "T+0d", "action": "Load and manifest" },
    { "milestone": "Suez Canal Entry", "eta": "T+18d", "action": "Submit canal clearance" },
    { "milestone": "Rotterdam ETA", "eta": "T+28d", "action": "Notify customs 48h prior" }
  ],
  "contingency_trigger": "If Red Sea threat level rises above 80%, re-route via Cape"
}
```

**Implementation location:** `app/agents/operations_agent.py` *(to be created)*

---

## ⚔️ Agent Debate Phase (To Be Implemented)

After all three agents produce their outputs, the system must execute a **structured debate** to surface conflicts and reach consensus.

**How the debate works:**

1. Each agent posts its top recommendation to a shared debate context
2. The orchestrator compares positions across three axes:
   - **Risk tolerance:** Risk Agent vs. Operations Agent (do they agree on threat severity?)
   - **Cost priority:** Cost Agent vs. Operations Agent (is the cheapest plan executable?)
   - **Risk vs. Cost conflict:** Risk Agent vs. Cost Agent (does cost optimization ignore critical risks?)
3. Conflicts are flagged for the Decision Engine
4. Agreements increase the final Decision confidence score

**Debate output schema:**
```json
{
  "agreements": [
    "All agents agree: Cape of Good Hope detour is operationally feasible"
  ],
  "conflicts": [
    {
      "between": ["Risk Agent", "Cost Agent"],
      "issue": "Cost Agent recommends Suez transit; Risk Agent flags 82% disruption risk",
      "resolution": "Risk Agent overrides — critical risk threshold (>65%) triggers veto"
    }
  ],
  "consensus_route": "Cape of Good Hope",
  "confidence_boost": 0.12
}
```

**Implementation location:** `app/agents/debate_engine.py` *(to be created)*

---

## 🔮 Scenario Simulation Engine (To Be Implemented)

The system must generate exactly **three forward-looking scenarios** for every analysis. Each scenario must be grounded in the data returned by the existing weather, news, historical, and geopolitical agents.

### Scenario Format

Each scenario must include:

| Field | Type | Description |
|---|---|---|
| `scenario_type` | string | `"BEST_CASE"` / `"MOST_LIKELY"` / `"WORST_CASE"` |
| `outcome` | string | Human-readable outcome description |
| `risk_level` | string | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| `eta_days` | int | Projected delivery time in days |
| `cost_usd` | int | Projected total cost in USD |
| `performance_score` | float | 0.0–1.0 efficiency score |
| `probability` | int | Likelihood this scenario occurs (%) |
| `triggers` | list | What would cause this scenario to occur |

### Example Scenarios (Shanghai → Rotterdam via Suez)

**Best Case (15% probability)**
```
Outcome: No disruptions; Suez clears normally; Rotterdam port uncongested
Risk Level: LOW
ETA: 24 days | Cost: $105,000 | Performance: 0.94
Triggers: ["Houthi ceasefire holds", "EU port strike resolves before ETA"]
```

**Most Likely (60% probability)**
```
Outcome: Minor Suez delay due to convoy queuing; Rotterdam has 2-day congestion
Risk Level: MEDIUM
ETA: 30 days | Cost: $128,000 | Performance: 0.78
Triggers: ["Standard operational variance", "Seasonal traffic at Suez"]
```

**Worst Case (25% probability)**
```
Outcome: Red Sea escalation forces Cape reroute; Rotterdam berth unavailable on arrival
Risk Level: CRITICAL
ETA: 42 days | Cost: $195,000 | Performance: 0.41
Triggers: ["Active Houthi missile engagement", "Rotterdam labor strike week 3"]
```

**Implementation location:** `app/agents/scenario_engine.py` *(to be created)*

---

## ✅ Decision Engine (To Be Implemented)

The Decision Engine synthesizes all agent outputs, debate results, and scenario simulations into a **single optimized decision**.

**Decision Engine logic:**

1. Read the debate consensus route
2. Weight it against the Most Likely scenario outcome
3. Apply confidence modifiers:
   - +0.10 if all 3 agents agree
   - +0.05 per matching historical memory case
   - −0.15 if a CRITICAL risk is present with no viable mitigation
4. Output the final decision with top 2–3 actionable recommendations

**Final Decision output schema:**
```json
{
  "final_route": "Cape of Good Hope",
  "decision_rationale": "82% geopolitical disruption risk at Suez exceeds acceptable threshold. Cape detour adds 14 days but removes CRITICAL risk exposure.",
  "recommendations": [
    {
      "rank": 1,
      "action": "Reroute immediately via Cape of Good Hope",
      "estimated_improvement": "Eliminates 35% delay risk, reduces insurance premium by $12,000"
    },
    {
      "rank": 2,
      "action": "Pre-clear Rotterdam customs 72h before arrival",
      "estimated_improvement": "Reduces port dwell time by 1.5 days (saves ~$6,500)"
    },
    {
      "rank": 3,
      "action": "Upgrade cargo insurance to All-Risk policy",
      "estimated_improvement": "Mitigates $95,000 worst-case cargo loss exposure"
    }
  ],
  "estimated_improvement_pct": 34,
  "confidence_score": 0.87
}
```

**Implementation location:** `app/agents/decision_engine.py` *(to be created)*

---

## 🧠 Explainable AI — XAI Layer (To Be Implemented)

Every final decision must be accompanied by a machine-readable, human-understandable explanation of **why** that decision was made and what factors contributed to it.

**XAI output format:**

```
DECISION: Reroute via Cape of Good Hope

TOP CONTRIBUTING FACTORS:
  1. Geopolitical Risk Score        → 38% weight  (82% disruption probability at Red Sea)
  2. Historical Delay Patterns      → 24% weight  (Suez routes avg +11 day delay in Q1)
  3. Cost-Risk Trade-off Analysis   → 19% weight  (Suez risk-adjusted cost > Cape base cost)
  4. Agent Debate Consensus         → 12% weight  (All 3 agents flagged Suez as high-risk)
  5. Weather Forecast (Dest.)       →  7% weight  (Rotterdam fog season adds 1.2 days avg)

KEY REASONING STEPS:
  Step 1: Risk Agent flags Red Sea as CRITICAL (>65% threshold)
  Step 2: Cost Agent calculates risk-adjusted Suez cost exceeds Cape cost by $28,000
  Step 3: Operations Agent confirms Cape route is fully viable with 0 blockers
  Step 4: Debate Engine reaches consensus: Cape of Good Hope
  Step 5: Scenario Engine confirms Cape route produces MEDIUM worst-case (vs. CRITICAL via Suez)
  Step 6: Memory recalls 3 similar past cases — Cape reroute reduced delay by avg 30%
  Step 7: Confidence score computed: 0.87 (HIGH)
```

**Implementation location:** `app/agents/xai_engine.py` *(to be created)*

---

## 🔁 What-If Analysis Engine (To Be Implemented)

The system must provide **at least 2 constraint variation scenarios** showing how the decision changes when key inputs shift.

### What-If Variation 1 — Budget Constraint Changed

```
IF: Maximum budget reduced from $195,000 → $130,000
THEN:
  - Cape of Good Hope route becomes cost-infeasible ($167,000 base + insurance)
  - Decision Engine shifts to: "Suez with enhanced security escort + upgraded insurance"
  - New confidence score: 0.61 (reduced from 0.87 due to CRITICAL risk not fully mitigated)
  - New ETA: 29 days | New Cost: $128,000
  - Risk Agent raises a HARD WARNING: CRITICAL risk remains unresolved at 82% probability
```

### What-If Variation 2 — Time Constraint Tightened

```
IF: Client SLA reduced from 35 days → 26 days hard deadline
THEN:
  - Cape of Good Hope (38 days) becomes deadline-infeasible
  - Decision Engine shifts to: "Air freight from Dubai → Rotterdam for final leg"
  - New cost: $285,000 (air cargo surcharge)
  - New ETA: 22 days | Risk Level: LOW
  - Cost Agent flags: 2.4× cost premium for 16-day time saving — trade-off score: 0.52
```

**Implementation location:** `app/agents/whatif_engine.py` *(to be created)*

---

## 🧬 Memory Simulation System (To Be Implemented)

The system must reference **similar past analyses** to improve decision confidence and provide institutional knowledge.

**How memory is used:**

1. On each new analysis, query the `analysis_results` MySQL table for past cases with matching:
   - Origin port / region
   - Destination port / region
   - Transport mode
   - Season / month window (±45 days)
2. If 1+ matching cases found, extract outcomes and compute average improvement metrics
3. Inject memory context into the XAI explanation and boost confidence score

**Memory reference output format:**

```
🧬 MEMORY INSIGHT:
  3 similar past scenarios found in institutional memory.

  Case M-047 (2025-11-12): Shanghai → Rotterdam via Suez
    → Suez disruption occurred; rerouted to Cape mid-voyage
    → Final delay: +9 days vs. +21 days projected via Suez
    → Memory confirms: Early Cape reroute reduces delay by avg 28%

  Case M-031 (2025-08-03): Ningbo → Hamburg via Suez
    → Red Sea threat forced last-minute reroute
    → Cost overrun: +$42,000 vs. $12,000 if rerouted proactively
    → Memory confirms: Proactive rerouting saves avg $30,000 vs. reactive

  CONFIDENCE BOOST from Memory: +0.08 (3 confirming cases)
  FINAL CONFIDENCE: 0.87
```

**Implementation location:** `app/agents/memory.py` *(extend existing file)*  
**Database table:** `analysis_memory` — new table to be added to `app/models/schema.sql`

**New `analysis_memory` table schema:**
```sql
CREATE TABLE analysis_memory (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    case_id       VARCHAR(10) UNIQUE NOT NULL,
    origin        VARCHAR(100),
    destination   VARCHAR(100),
    transport_mode ENUM('road','maritime','air'),
    analysis_month TINYINT,
    final_route   VARCHAR(200),
    risk_level    ENUM('LOW','MEDIUM','HIGH','CRITICAL'),
    outcome_delay_days INT,
    outcome_cost_usd   INT,
    improvement_pct    FLOAT,
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔄 Real-Time Adaptability (To Be Implemented)

The system must be capable of **dynamically re-triggering analysis** when input parameters shift mid-session.

**Adaptation triggers:**

| Trigger | Adaptation Action |
|---|---|
| Weather API returns storm alert on route | Re-run Scenario Engine with elevated weather risk weight |
| News Agent detects breaking geopolitical event | Re-run Risk Analyst Agent; re-debate if risk level changes |
| User changes budget via UI slider | Re-run What-If Engine for new budget constraint |
| Vessel AIS shows unexpected deviation | Notify user; re-compute ETA with current position |
| Port congestion index rises > 80% | Trigger alternate port evaluation (e.g., Antwerp vs. Rotterdam) |

**Implementation:** Add a `/api/adapt/<session_id>` SSE endpoint that listens for and re-streams updated analysis when adaptation triggers fire.

**Implementation location:** `app/routes/api.py` *(extend existing file)*

---

## 📋 Output Format — Full Structured Response

Every call to `/api/analyze` must return a response conforming to this complete structure:

```json
{
  "session_id": "abc-123",
  "query": "Electronics from Shanghai to Rotterdam via Suez, 28 days",
  "transport_mode": "maritime",
  "risk_analysis": {
    "risks": [ { "risk_id": "...", "category": "...", "probability": 82, "severity": "CRITICAL" } ],
    "critical_count": 1,
    "overall_risk_score": 74
  },
  "agent_insights": {
    "risk_agent": { "summary": "...", "top_risk": "...", "recommendation": "..." },
    "cost_agent": { "summary": "...", "cheapest_option": "...", "recommendation": "..." },
    "operations_agent": { "summary": "...", "feasibility": "HIGH", "recommendation": "..." }
  },
  "debate_summary": {
    "agreements": ["..."],
    "conflicts": [{ "between": ["..."], "issue": "...", "resolution": "..." }],
    "consensus_route": "..."
  },
  "scenarios": {
    "best_case": { "outcome": "...", "risk_level": "LOW", "eta_days": 24, "cost_usd": 105000, "probability": 15 },
    "most_likely": { "outcome": "...", "risk_level": "MEDIUM", "eta_days": 30, "cost_usd": 128000, "probability": 60 },
    "worst_case": { "outcome": "...", "risk_level": "CRITICAL", "eta_days": 42, "cost_usd": 195000, "probability": 25 }
  },
  "final_decision": {
    "route": "Cape of Good Hope",
    "rationale": "...",
    "recommendations": [ { "rank": 1, "action": "...", "estimated_improvement": "..." } ],
    "estimated_improvement_pct": 34,
    "confidence_score": 0.87
  },
  "xai": {
    "contributing_factors": [ { "factor": "Geopolitical Risk", "weight_pct": 38, "detail": "..." } ],
    "reasoning_steps": ["Step 1: ...", "Step 2: ..."]
  },
  "whatif_analysis": [
    { "constraint": "Budget reduced to $130,000", "new_decision": "...", "new_confidence": 0.61 },
    { "constraint": "SLA tightened to 26 days", "new_decision": "...", "new_confidence": 0.73 }
  ],
  "memory_insight": {
    "matched_cases": 3,
    "confidence_boost": 0.08,
    "cases": [ { "case_id": "M-047", "summary": "..." } ]
  }
}
```

---

## 🗂 Files To Be Created

The following new files must be created to implement this system. **No existing files should be modified** unless explicitly noted.

| File | Purpose |
|---|---|
| `app/agents/risk_analyst_agent.py` | Risk Analyst Agent — probability scoring, CRITICAL flagging |
| `app/agents/cost_optimization_agent.py` | Cost Optimization Agent — financial impact and trade-off analysis |
| `app/agents/operations_agent.py` | Operations Agent — feasibility check and execution plan |
| `app/agents/debate_engine.py` | Agent Debate Phase — conflict detection and consensus resolution |
| `app/agents/scenario_engine.py` | Scenario Simulation Engine — Best/Most Likely/Worst case generation |
| `app/agents/decision_engine.py` | Decision Engine — final route decision and recommendation synthesis |
| `app/agents/xai_engine.py` | XAI Layer — contributing factors and reasoning step generation |
| `app/agents/whatif_engine.py` | What-If Engine — constraint variation scenario analysis |

**Existing files to extend (minimally):**

| File | Extension Required |
|---|---|
| `app/agents/memory.py` | Add `query_memory()` and `store_memory()` functions for the new `analysis_memory` table |
| `app/models/schema.sql` | Add `analysis_memory` table definition |
| `app/routes/api.py` | Include new agent outputs in the `/api/analyze` response; add `/api/adapt/<session_id>` endpoint |
| `app/agents/graph.py` | Wire new agents (Risk, Cost, Operations, Debate, Scenario, Decision, XAI, WhatIf) into the orchestration graph |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.10+, Flask 3.0 | REST API, SSE streaming, routing engine |
| **LLM** | Groq (Llama 3.1 8B) | Agent routing, risk synthesis, debate resolution, XAI narrative |
| **Database** | MySQL 8.0 | Caching, history, memory, analytics, analysis_memory |
| **Frontend** | Vanilla JS, Leaflet.js | Interactive dashboard, map simulation, what-if sliders |
| **APIs** | OpenWeather, Tavily, OSRM, AISStream | Real-time data sources for agent intelligence |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- MySQL 8.0+ (running locally)
- Free API keys from: [Groq](https://console.groq.com), [OpenWeather](https://openweathermap.org/api), [Tavily](https://tavily.com)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd shipment_risk_agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys and MySQL credentials

# 5. Seed historical data (optional but recommended)
python seed_data.py

# 6. Run the server
python run.py
```

### Access
- **Dashboard**: http://127.0.0.1:5000
- **Health Check**: http://127.0.0.1:5000/health
- **API**: POST http://127.0.0.1:5000/api/analyze

---

## Usage Flow

1. **Enter a query** — e.g., *"Container shipment from Shanghai to Rotterdam via sea in 28 days"*
2. **Watch agents reason** — Live SSE feed shows all 11 agents' decisions including debate
3. **See the route** — Animated vehicle traversal with AI checkpoint narration
4. **Review the full decision output** — Risk registry, scenarios, XAI factors, confidence score
5. **Explore What-If variations** — Adjust budget/time sliders to re-run constraint analysis
6. **Review memory insights** — See how past similar cases informed this decision

### Example Queries

| Query | Mode | Agents Active | Key Output |
|---|---|---|---|
| `Shipment from Delhi to Bangalore, textiles` | 🚗 Road | Weather, News, Historical, Risk, Cost, Ops | Low-risk road decision, 0.91 confidence |
| `Electronics from Shanghai to Rotterdam via Suez` | 🚢 Maritime | All 11 agents + Plan B + Debate | Cape reroute recommended, 0.87 confidence |
| `Cargo from Delhi to London by air` | ✈ Air | Weather, News, Historical, Risk, Cost, Ops | Air viable, cost vs. speed XAI breakdown |

---

## Project Structure

```
shipment_risk_agent/
├── run.py                       # Application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── seed_data.py                 # Historical data seeder
│
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration from env vars
│   ├── database.py              # MySQL connection pool
│   │
│   ├── agents/
│   │   ├── graph.py             # LangGraph-style orchestrator [EXTEND]
│   │   ├── router.py            # LLM-based agent router
│   │   ├── brain.py             # Central reasoning engine
│   │   ├── intake_agent.py      # Query parser
│   │   ├── weather_agent.py     # OpenWeather integration
│   │   ├── news_agent.py        # News disruption scanner
│   │   ├── historical_agent.py  # Delay pattern analysis
│   │   ├── vessel_agent.py      # AIS vessel tracking
│   │   ├── port_intel_agent.py  # Port intelligence
│   │   ├── geopolitical_agent.py# Sanctions/conflict risk
│   │   ├── memory.py            # Institutional memory [EXTEND]
│   │   ├── crew.py              # Validators & scorers
│   │   ├── state.py             # Shared state definition
│   │   │
│   │   │   ── NEW FILES TO CREATE ──
│   │   ├── risk_analyst_agent.py    # [NEW] Risk scoring + CRITICAL flagging
│   │   ├── cost_optimization_agent.py # [NEW] Financial impact + trade-offs
│   │   ├── operations_agent.py      # [NEW] Feasibility + execution plan
│   │   ├── debate_engine.py         # [NEW] Agent debate + consensus
│   │   ├── scenario_engine.py       # [NEW] Best/Likely/Worst simulation
│   │   ├── decision_engine.py       # [NEW] Final decision synthesis
│   │   ├── xai_engine.py            # [NEW] Explainability layer
│   │   └── whatif_engine.py         # [NEW] Constraint variation analysis
│   │
│   ├── tools/                   # Tool wrappers for agents
│   ├── routes/
│   │   ├── api.py               # REST API + SSE + routing [EXTEND]
│   │   └── main.py              # Dashboard page
│   │
│   ├── models/
│   │   └── schema.sql           # Database schema [EXTEND: add analysis_memory]
│   │
│   └── templates/               # Jinja2 HTML templates
│
└── static/
    ├── css/main.css             # UI styles
    └── js/main.js               # Frontend logic + Leaflet
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze` | Start analysis → returns full Decision Intelligence output |
| `GET` | `/api/stream/<session_id>` | SSE stream of all agent reasoning (incl. debate + XAI) |
| `GET` | `/api/result/<session_id>` | Get completed analysis result |
| `GET` | `/api/adapt/<session_id>` | SSE stream for real-time re-analysis on trigger events **[NEW]** |
| `GET` | `/api/history` | List recent analyses |
| `GET` | `/api/route?origin=X&dest=Y` | Compute route with waypoints |
| `GET` | `/api/analytics` | System-wide statistics |
| `GET` | `/api/tools` | List registered agent tools |
| `POST` | `/api/feedback` | Submit outcome feedback |
| `GET` | `/health` | Health check |

---

## Future Improvements

- [ ] **Containerization** — Docker + docker-compose for one-command setup
- [ ] **Production WSGI** — Gunicorn with gevent workers for SSE scaling
- [ ] **Rate limiting** — Flask-Limiter on API endpoints
- [ ] **WebSocket upgrade** — Replace SSE polling with true WebSocket for bidirectional comms
- [ ] **Maritime API** — Integrate SeaRoutes or MarineTraffic for production-grade vessel routing
- [ ] **CI/CD pipeline** — GitHub Actions with test suite and deployment
- [ ] **Multi-user auth** — JWT-based authentication for production use
- [ ] **Cost tracking dashboard** — Track LLM token usage and API call costs
- [ ] **Expanded What-If UI** — Budget/time sliders on the dashboard for live re-analysis
- [ ] **Memory visualization** — Timeline view of past similar cases in the dashboard
- [ ] **Agent debate replay** — Expandable debate transcript panel in the UI

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for the Agentic AI Hackathon 2026*
