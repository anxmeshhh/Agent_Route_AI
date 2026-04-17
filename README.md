<div align="center">

# 🚢 AgentRouteAI

### Predictive Shipment Delay & Risk Intelligence — Powered by Agentic AI

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://mysql.com)
[![Groq](https://img.shields.io/badge/Groq-LLaMA3-F55036?style=for-the-badge)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

---

*Autonomous supply chain intelligence. Real-time risk. Actionable mitigations.*

**Team Error:200** · Built for the Predictive Delay & Risk Intelligence Hackathon Track

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [8-Agent Pipeline](#-8-agent-pipeline)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker Deployment](#docker-deployment)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [Database Schema](#-database-schema)
- [Security](#-security)
- [Roadmap](#-roadmap)
- [Team](#-team)
- [Acknowledgments](#-acknowledgments)

---

## 🌐 Overview

**AgentRouteAI** is a production-grade, multi-agent AI platform that provides real-time shipment delay and risk intelligence across **road, sea, and air** transport modes. Unlike rule-based systems, AgentRouteAI deploys a **graph-orchestrated crew of 8 specialized AI agents** that reason autonomously, cross-validate each other's signals, and synthesize a unified risk assessment with precision-targeted mitigation strategies.

The system eliminates guesswork from supply chain decisions by delivering:

- **Live weather, geopolitical, and news intelligence** correlated against your shipment's exact route
- **Multi-agent signal cross-validation** — agents actively challenge each other's findings before forming conclusions
- **Mode-aware ETA and cost modeling** — no more maritime-biased logic applied to road or air shipments
- **Real-time agent reasoning transparency** streamed live to the dashboard via Server-Sent Events

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **8-Agent Orchestration** | Specialized agents for intake, weather, news, historical, vessel, port intel, geopolitical, and risk synthesis |
| 🔀 **LLM-Based Routing** | Groq (LLaMA 3) dynamically selects the optimal agent chain based on query complexity |
| 📡 **Live Reasoning Stream** | Agent logs stream to the UI in real-time over SSE — full transparency of the AI's thinking |
| 🗺️ **Multi-Modal Routing** | OSRM road routing, sea-lane maritime paths, and great-circle air routes |
| 🧠 **Agentic Memory** | Past analyses recalled for similar routes, improving decision quality over time |
| 👥 **Multi-Tenant RBAC** | Organization-scoped data isolation with role-based access (User / Admin / Super Admin) |
| 🔐 **Defense-in-Depth Security** | Fernet encryption, bcrypt passwords, HttpOnly JWTs, MFA-OTP, refresh token rotation |
| 🐳 **Containerized Deployment** | One-command Docker Compose stack: MySQL + Backend + Nginx frontend |
| 📊 **Super Admin Dashboard** | Full CRUD analytics, live system logs, agent metrics, and user management |

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          FRONTEND LAYER                              │
│   Nginx (Port 8080)  ·  Leaflet Maps  ·  SSE Consumer  ·  Jinja2   │
└──────────────────────┬───────────────────────────────────────────────┘
                       │  HTTP / SSE
┌──────────────────────▼───────────────────────────────────────────────┐
│                         BACKEND LAYER                                │
│   Flask / Gunicorn (Port 5000)                                       │
│   ├── Auth Routes       (JWT · OTP · OAuth2 / Google)               │
│   ├── Analyze Routes    (POST /api/analyze → kicks off pipeline)     │
│   ├── Stream Routes     (GET /api/stream/:id → SSE event source)    │
│   ├── Admin Routes      (Super Admin CRUD dashboard)                 │
│   └── History / Ticket / Analytics / Tools Routes                   │
└──────────────────────┬───────────────────────────────────────────────┘
                       │  In-process async threads
┌──────────────────────▼───────────────────────────────────────────────┐
│                         WORKER LAYER                                 │
│   app/worker — 8-Agent LangGraph Pipeline                            │
│   ├── IntakeAgent       →  Parses & structures user query            │
│   ├── WeatherAgent      →  OpenWeatherMap conditions                 │
│   ├── NewsAgent         →  Tavily real-time news search              │
│   ├── HistoricalAgent   →  MySQL delay pattern recall                │
│   ├── VesselAgent       →  AISStream vessel tracking                 │
│   ├── PortIntelAgent    →  Congestion, wait times, advisories        │
│   ├── GeopoliticalAgent →  Sanctions, chokepoints, conflict zones    │
│   └── RiskAgent + Crew  →  Synthesis · Confidence · Mitigation      │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│                        DATA LAYER                                    │
│   MySQL 8.0 (Pool: 15 connections)                                   │
│   12 Tables: users · shipments · risk_assessments ·                 │
│              agent_logs · weather_cache · news_cache ·               │
│              historical_shipments · analysis_memory · ...            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 8-Agent Pipeline

The core of AgentRouteAI is a **LangGraph-style directed graph** where agents run both in parallel where possible and sequentially where dependencies exist.

```
Query Input
    │
    ▼
┌─────────────┐
│ IntakeAgent │  →  Parses origin/dest/mode/cargo/ETA from natural language
└──────┬──────┘
       │
       ├──────────────────────────────────────────────────────┐
       │ (Parallel execution)                                 │
       ▼                          ▼                           ▼
┌─────────────┐          ┌───────────────┐          ┌─────────────────┐
│ WeatherAgent│          │ NewsAgent     │          │ HistoricalAgent │
└──────┬──────┘          └───────┬───────┘          └────────┬────────┘
       │                         │                           │
       ├────────────┬────────────┘                           │
       ▼            ▼                                        │
┌──────────┐  ┌──────────────┐  ┌──────────────────┐        │
│ Vessel   │  │ Port Intel   │  │  Geopolitical    │        │
│ Agent    │  │ Agent        │  │  Agent           │        │
└────┬─────┘  └──────┬───────┘  └────────┬─────────┘        │
     └───────────────┴──────────────────┬─┘                  │
                                        │ ◄──────────────────┘
                                        ▼
                              ┌─────────────────┐
                              │   Risk Agent    │  ←  Signal aggregation
                              │   + Crew        │  ←  Cross-validation
                              │   (Synthesis)   │  ←  Confidence scoring
                              └────────┬────────┘  ←  Mitigation strategy
                                       │
                                       ▼
                              Final Risk Assessment
                              (Score / Threats / Suggestions / Intel)
```

### Crew AI Components

| Component | Role |
|---|---|
| **SignalValidator** | Cross-checks signals from all agents; detects contradictions |
| **ConflictResolver** | Applies rule-based + LLM reasoning to resolve disagreements |
| **ConfidenceScorer** | Scores data freshness, coverage, agreement, and LLM quality |
| **MitigationStrategist** | Generates ranked, context-specific actionable mitigations |

---

## 📁 Project Structure

```
shipment_risk_agent/
│
├── app/                          # Main application package
│   ├── __init__.py               # Flask application factory
│   │
│   ├── worker/                   # 🤖 Agentic AI engine
│   │   ├── agents/
│   │   │   ├── graph.py          # LangGraph-style orchestrator
│   │   │   ├── crew.py           # Signal validation & confidence scoring
│   │   │   ├── router.py         # LLM-based dynamic task router
│   │   │   ├── brain.py          # Central reasoning coordinator
│   │   │   ├── state.py          # Shared AgentState schema
│   │   │   ├── memory.py         # Analysis memory + recall
│   │   │   ├── intake_agent.py
│   │   │   ├── weather_agent.py
│   │   │   ├── news_agent.py
│   │   │   ├── historical_agent.py
│   │   │   ├── vessel_agent.py
│   │   │   ├── port_intel_agent.py
│   │   │   ├── geopolitical_agent.py
│   │   │   └── risk_agent.py
│   │   └── tools/
│   │       ├── registry.py       # Tool registration & discovery
│   │       ├── weather_tool.py
│   │       ├── news_tool.py
│   │       ├── historical_tool.py
│   │       ├── vessel_tool.py
│   │       ├── port_intel_tool.py
│   │       ├── geopolitical_tool.py
│   │       └── memory_tool.py
│   │
│   ├── backend/                  # 🔧 API & data layer
│   │   ├── routes/
│   │   │   ├── api.py            # Blueprint registry
│   │   │   ├── main.py           # HTML page routes
│   │   │   ├── analyze_routes.py # POST /api/analyze pipeline
│   │   │   ├── stream_routes.py  # SSE event stream
│   │   │   ├── auth_routes.py    # Auth endpoints (JWT / OAuth2 / OTP)
│   │   │   ├── admin_routes.py   # Super Admin dashboard API
│   │   │   ├── ticket_routes.py  # Shipment ticket management
│   │   │   ├── history_routes.py
│   │   │   ├── analytics_routes.py
│   │   │   ├── route_engine.py   # Unified routing orchestrator
│   │   │   ├── _road_routing.py  # OSRM-based road routing
│   │   │   ├── _maritime_routing.py
│   │   │   └── _air_routing.py   # Great-circle air paths
│   │   ├── auth/
│   │   │   ├── crypto.py         # Fernet, bcrypt, JWT utilities
│   │   │   └── decorators.py     # @login_required, @admin_required
│   │   ├── models/
│   │   │   ├── schema.sql        # 12-table MySQL schema
│   │   │   └── ref_data.py       # In-memory reference data cache
│   │   ├── config.py             # Environment-based configuration
│   │   └── database.py           # MySQL connection pool (15 conn)
│   │
│   └── frontend/                 # 🎨 UI assets
│       ├── templates/            # Jinja2 HTML templates
│       │   ├── base.html
│       │   ├── index.html        # Main shipment dashboard
│       │   ├── analysis.html     # Risk analysis & Intel tabs
│       │   ├── login.html
│       │   ├── signup.html
│       │   └── admin.html        # Super Admin dashboard
│       └── static/
│           ├── css/              # Dark-theme component styles
│           └── js/main.js        # SSE consumer + UI orchestration
│
├── docker/
│   ├── frontend/
│   │   ├── Dockerfile            # Nginx image
│   │   └── nginx.conf            # SSE-aware reverse proxy config
│   └── mysql/
│       └── init.sql              # DB & user init on first start
│
├── debug/                        # 🛠️ Dev & maintenance scripts (isolated)
│   └── *.py                      # migrate, patch, verify, seed scripts
│
├── Dockerfile                    # Backend image (Python 3.12 + Gunicorn)
├── docker-compose.yml            # Full stack: MySQL + Backend + Nginx
├── wsgi.py                       # Gunicorn WSGI entrypoint
├── run.py                        # Flask dev server
├── requirements.txt
└── .env.example                  # Environment template
```

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Required |
| MySQL | 8.0+ | Local or Docker |
| Groq API Key | — | [groq.com](https://groq.com) · free tier available |
| Docker & Compose | 24.x+ | For containerized deployment only |

---

### Local Development

**1. Clone the repository**

```bash
git clone https://github.com/anxmeshhh/Agent_Route_AI.git
cd Agent_Route_AI/shipment_risk_agent
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment**

```bash
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section)
```

**5. Run the development server**

```bash
python run.py
```

The application starts at **http://127.0.0.1:5000**

---

### Docker Deployment

One command brings up the entire stack:

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env — set GROQ_API_KEY, SECRET_KEY, etc.

# 2. Build and start all services
docker-compose up --build -d

# 3. Check service health
docker-compose ps

# 4. Tail logs
docker-compose logs -f backend
```

**Service Ports (Docker):**

| Service | Host Port | Description |
|---|---|---|
| Frontend (Nginx) | `8080` | Public-facing entry point |
| Backend (Gunicorn) | Internal only | Proxied via Nginx |
| MySQL | `3307` | Exposed for local DB tools |

> **Note:** Port 3307 is used to avoid conflicts with any local MySQL instance.

**Stop the stack:**

```bash
docker-compose down          # Stop containers (keep data)
docker-compose down -v       # Stop and delete MySQL volume
```

---

## 🔑 Environment Variables

Copy `.env.example` and populate all values:

```bash
# ── Flask ────────────────────────────────────────────────────
SECRET_KEY=your-32-char-secret-key-here
FLASK_ENV=development

# ── MySQL ────────────────────────────────────────────────────
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_db_user
MYSQL_PASSWORD=your_db_password
MYSQL_DATABASE=shipment_risk_db

# ── Groq LLM ─────────────────────────────────────────────────
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama3-8b-8192

# ── Encryption ───────────────────────────────────────────────
FERNET_KEY=your-fernet-key           # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# ── External APIs (optional) ─────────────────────────────────
OPENWEATHER_API_KEY=your-key
TAVILY_API_KEY=your-key
AISSTREAM_API_KEY=your-key

# ── OAuth2 (optional) ────────────────────────────────────────
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Service health check |
| `GET` | `/` | Required | Main shipment dashboard |
| `GET` | `/analysis` | Required | Risk analysis view |
| `GET` | `/admin` | Super Admin | Admin dashboard |
| `POST` | `/api/analyze` | Required | Start analysis pipeline |
| `GET` | `/api/stream/:id` | Required | SSE reasoning stream |
| `POST` | `/api/auth/login` | None | Login (JWT issued) |
| `POST` | `/api/auth/signup` | None | Register user |
| `POST` | `/api/auth/logout` | Required | Invalidate session |
| `GET` | `/api/auth/me` | Required | Current user profile |
| `GET` | `/api/history` | Required | Past analyses |
| `GET` | `/api/tools` | Required | Registered agent tools |
| `GET` | `/api/analytics` | Admin | Platform analytics |
| `GET` | `/api/route` | Required | Route geometry |

---

## 🗄️ Database Schema

Twelve tables covering the full application lifecycle:

| Table | Purpose |
|---|---|
| `organisations` | Multi-tenant root entity |
| `users` | User accounts with encrypted PII |
| `mfa_otp` | 6-digit one-time passwords (5-min TTL) |
| `refresh_tokens` | Hashed JWT refresh tokens |
| `shipments` | One row per analysis session |
| `risk_assessments` | Final risk output per session |
| `agent_logs` | Every agent action (streamed live) |
| `weather_cache` | Cached weather results (1-hr TTL) |
| `news_cache` | Tavily search results (6-hr TTL) |
| `historical_shipments` | Seeded delay history by lane |
| `analysis_memory` | Past analyses indexed for recall |
| `prediction_outcomes` | Actual outcomes for accuracy tracking |

---

## 🔐 Security

AgentRouteAI implements **defense-in-depth** aligned with GDPR Article 32 and India's DPDP Act 2023.

### Data at Rest

| Data | Protection |
|---|---|
| Passwords | bcrypt · 12 rounds |
| Email addresses | Fernet (AES-128-CBC + HMAC-SHA256) + SHA-256 blind index |
| Organisation names | Fernet encryption |
| Refresh tokens | SHA-256 hashed before storage |
| API credentials | Environment variables only |

### Data in Transit

- **HttpOnly, Secure, SameSite=Strict** cookies prevent XSS and CSRF
- **HTTPS enforced** in production via Nginx reverse proxy
- **CORS** scoped to trusted origins only

### Access Control

- **Multi-tenant isolation** — all queries scoped to the authenticated org
- **RBAC** via `@login_required`, `@admin_required`, `@superadmin_required`
- **Refresh token rotation** on every use prevents replay attacks
- **Super Admin bypass** — privileged account skips OTP for direct access

---

## 🗺️ Roadmap

### Near-Term
- [ ] WebSocket support alongside SSE for bidirectional streaming
- [ ] Prometheus `/metrics` endpoint for observability
- [ ] Structured JSON logging with `structlog`
- [ ] Integration tests against live APIs (nightly CI)

### Medium-Term
- [ ] Redis-backed SSE adapter for horizontal scaling
- [ ] Celery workers for true async agent execution
- [ ] Real AIS API integration (MarineTraffic / VesselFinder)
- [ ] KMS integration (AWS KMS / HashiCorp Vault)
- [ ] Fine-grained RBAC with custom permission sets

### Long-Term
- [ ] Fine-tuned domain model for risk synthesis
- [ ] Multi-modal input (PDF bills of lading, shipping documents)
- [ ] Predictive route optimization via reinforcement learning
- [ ] Public Python & TypeScript SDK
- [ ] Public API with rate limiting and billing

---

## 👥 Team

<div align="center">

### **Team Error:200** 🚀

*Where HTTP 200 meets zero errors*

</div>

| Member | Role |
|---|---|
| **Animesh Gupta** | Lead Engineer · Agentic AI Architecture · Backend Systems |
| **Apurva Singh** | Frontend Engineering · UI/UX · SSE Integration |
| **Aditya Nair** | DevOps · Infrastructure · Data Pipeline |

---

## 🙏 Acknowledgments

- **[Groq](https://groq.com)** — Lightning-fast LLM inference at 300+ tok/s
- **[OpenWeatherMap](https://openweathermap.org)** — Real-time weather data
- **[Tavily](https://tavily.com)** — Intelligent real-time search API
- **[AISStream](https://aisstream.io)** — Free vessel AIS telemetry
- **[OSRM](https://project-osrm.org)** — Open-source road routing engine
- **[Leaflet.js](https://leafletjs.com)** — Interactive mapping library
- **[OpenStreetMap](https://openstreetmap.org)** — Global open map data

---

## 📸 Screenshots

<img width="1600" alt="Dashboard" src="https://github.com/user-attachments/assets/0f8daa29-ac0b-440d-b3b2-dfac5adcdbd2" />
<img width="679" alt="Analysis" src="https://github.com/user-attachments/assets/6cab30f9-f482-4ea9-9d93-fda55ded59e0" />
<img width="1600" alt="Risk Intel" src="https://github.com/user-attachments/assets/7c80b11b-412f-42bf-a5bb-319637644230" />
<img width="1600" alt="Route Map" src="https://github.com/user-attachments/assets/7f3f5650-33fa-4625-851a-3721edad6c29" />
<img width="1600" alt="Agent Logs" src="https://github.com/user-attachments/assets/eee222ae-34dc-4e82-89da-64c0042ca90c" />

---

<div align="center">

## Video


**Built with ❤️ by Team Error:200 — for the future of autonomous supply chain intelligence**

*AgentRouteAI · Because shipments shouldn't be guesswork.*

[⬆ Back to top](#-agentrouteai)

</div>
