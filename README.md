# 🗺 AgentRouteAI — Agentic Shipment Risk Intelligence

> **8-agent AI system** that predicts shipment delays, assesses route risk, and simulates real-time transport across Road, Maritime, and Air corridors — with live reasoning transparency.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama3-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Problem Statement

Global supply chain managers face **$1.6 trillion in annual losses** from shipment delays, unpredictable weather, port congestion, and geopolitical disruptions. Existing tools provide static ETAs without understanding the *why* behind delays or offering intelligent alternatives.

**AgentRouteAI** solves this with an **agentic AI system** — 8 specialized agents autonomously gather intelligence, reason about risk, and deliver actionable mitigation strategies in real-time.

---

## Key Features

| Feature | Description |
|---|---|
| 🧠 **Agentic Router** | LLM-based brain that decides which agents to invoke based on transport context — skips irrelevant agents (e.g., vessel tracking for road routes) |
| 🗺 **Multi-Modal Routing** | Road (OSRM), Maritime (chokepoint-based), Air (great-circle) — auto-detected from query |
| 🛡 **Plan B Routes** | Alternate routes computed for high-risk maritime corridors (Suez → Cape, Panama → Horn) |
| 🌡 **Real-Time Weather** | Live OpenWeather API data on destination markers |
| 📰 **News Intelligence** | Tavily-powered disruption scanning for route-relevant news |
| 📊 **Historical Analysis** | MySQL-backed delay pattern analysis by port, season, and cargo type |
| 🚢 **Vessel Tracking** | AIS-based vessel position and ETA verification |
| 🌍 **Geopolitical Risk** | Sanctions, conflict zones, and regulatory risk assessment |
| 🔄 **Live Simulation** | Animated vehicle traversal with AI checkpoint narration |
| 💾 **Memory & Learning** | Past analyses recalled for institutional knowledge |
| ⚡ **SSE Streaming** | Real-time reasoning transparency — watch agents think live |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Flask Web Server                       │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ Dashboard │  │ SSE Streaming │  │  REST API Layer  │  │
│  └────┬─────┘  └───────┬───────┘  └────────┬─────────┘  │
│       └────────────────┼───────────────────┘             │
│                        ▼                                  │
│              ┌─────────────────┐                         │
│              │  Agent Graph    │ ← LangGraph-style       │
│              │  Orchestrator   │   state machine          │
│              └────────┬────────┘                         │
│       ┌───────────────┼───────────────┐                  │
│       ▼               ▼               ▼                  │
│  ┌─────────┐   ┌───────────┐   ┌──────────┐            │
│  │ Intake  │   │  Router   │   │  Brain   │             │
│  │ Agent   │   │  (LLM)    │   │  (Groq)  │             │
│  └─────────┘   └─────┬─────┘   └──────────┘            │
│                       │                                   │
│    ┌──────┬──────┬────┴────┬──────┬──────┬──────┐       │
│    ▼      ▼      ▼         ▼      ▼      ▼      ▼       │
│  Weather News  History  Vessel  Port  Geopolitical       │
│  Agent   Agent  Agent   Agent   Intel  Agent             │
│    ▼      ▼      ▼         ▼      ▼      ▼              │
│  [OWM]  [Tavily] [MySQL] [AIS] [Intel] [Analysis]       │
└──────────────────────┬──────────────────────────────────┘
                       ▼
              ┌────────────────┐
              │  MySQL (InnoDB)│
              │  7 tables      │
              └────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python 3.10+, Flask 3.0 | REST API, SSE streaming, routing engine |
| **LLM** | Groq (Llama 3.1 8B) | Agent routing, risk synthesis, narrative generation |
| **Database** | MySQL 8.0 | Caching, history, memory, analytics |
| **Frontend** | Vanilla JS, Leaflet.js | Interactive dashboard, map simulation |
| **APIs** | OpenWeather, Tavily, OSRM, AISStream | Real-time data sources |

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
2. **Watch agents reason** — Live SSE feed shows each agent's decisions
3. **See the route** — Animated vehicle traversal with AI checkpoint narration
4. **Review risk assessment** — Score, factors, and mitigation strategies
5. **Explore alternatives** — Plan B routes for high-risk corridors

### Example Queries
| Query | Mode Detected | Agents Used |
|---|---|---|
| `Shipment from Delhi to Bangalore, textiles` | 🚗 Road | Weather, News, Historical (vessel/port skipped) |
| `Electronics from Shanghai to Rotterdam via Suez` | 🚢 Maritime | All 7 agents + Plan B route |
| `Cargo from Delhi to London by air` | ✈ Air | Weather, News, Historical (vessel skipped) |

---

## Project Structure

```
shipment_risk_agent/
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
├── seed_data.py              # Historical data seeder
│
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuration from env vars
│   ├── database.py           # MySQL connection pool
│   │
│   ├── agents/               # 8 specialized AI agents
│   │   ├── graph.py          # LangGraph-style orchestrator
│   │   ├── router.py         # LLM-based agent router
│   │   ├── brain.py          # Central reasoning engine
│   │   ├── intake_agent.py   # Query parser
│   │   ├── weather_agent.py  # OpenWeather integration
│   │   ├── news_agent.py     # News disruption scanner
│   │   ├── historical_agent.py # Delay pattern analysis
│   │   ├── vessel_agent.py   # AIS vessel tracking
│   │   ├── port_intel_agent.py # Port intelligence
│   │   ├── geopolitical_agent.py # Sanctions/conflict risk
│   │   ├── memory.py         # Institutional memory
│   │   ├── crew.py           # Validators & scorers
│   │   └── state.py          # Shared state definition
│   │
│   ├── tools/                # Tool wrappers for agents
│   ├── routes/               # Flask endpoints
│   │   ├── api.py            # REST API + SSE + routing
│   │   └── main.py           # Dashboard page
│   │
│   ├── models/
│   │   └── schema.sql        # Database schema (7 tables)
│   │
│   └── templates/            # Jinja2 HTML templates
│
└── static/
    ├── css/main.css          # UI styles
    └── js/main.js            # Frontend logic + Leaflet
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analyze` | Start a new analysis (body: `{"query": "..."}`) |
| `GET` | `/api/stream/<session_id>` | SSE stream of agent reasoning |
| `GET` | `/api/result/<session_id>` | Get completed analysis result |
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

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for the Agentic AI Hackathon 2026*
