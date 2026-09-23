# Enterprise AI Governance & Compliance Agent

> **"Agents produce evidence. Deterministic governance logic produces the final decision."**

A production-grade prototype of an Enterprise AI Governance & Compliance platform built for portfolio/interview demonstration.

---

## Architecture

```
AI Application Input
        │
        ▼
┌─────────────────────────────────────────┐
│      Governance Orchestrator            │
│           (LangGraph)                   │
│                                         │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │  Policy  │  │  Privacy   Security  │ │
│  │   RAG    │  │  Agent     Agent     │ │
│  │ Retrieve │  │  (PII)     (Inject.) │ │
│  └──────────┘  └──────────────────────┘ │
│                         │               │
│               Policy Compliance Agent   │
│                         │               │
│               ┌─────────▼──────────┐    │
│               │  Structured        │    │
│               │  Evidence/Findings │    │
│               └─────────┬──────────┘    │
│                         │               │
│               ┌─────────▼──────────┐    │
│               │  Deterministic     │    │
│               │  Risk Engine       │    │
│               └─────────┬──────────┘    │
│                         │               │
│               ALLOW | REVIEW | BLOCK    │
└─────────────────────────────────────────┘
        │             │            │
   Audit Log   Human Approval   Audit Log
```

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **LLMs produce evidence** | Agents classify, reason, and summarize — they don't make final decisions |
| **Deterministic governance** | Risk engine uses configurable weights and thresholds — no LLM in the decision path |
| **Least privilege** | Agents access data through typed MCP tools, not raw SQL |
| **Auditability** | Every governance action writes an immutable `AuditEvent` |
| **Provider abstraction** | Swap Groq ↔ Ollama by changing one env var |
| **Human-in-the-loop** | REVIEW decisions require explicit human approval before proceeding |
| **Exception management** | Time-bound exceptions with mandatory expiration — no permanent silent bypasses |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Package manager | uv |
| Web framework | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| Orchestration | LangGraph |
| LLM (primary) | Groq API (free credits) |
| LLM (fallback) | Ollama (local) |
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| Embeddings | SentenceTransformers (`all-MiniLM-L6-v2`) — local, no cost |
| Observability | LangSmith (optional) |
| Logging | structlog |

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── config/        # Settings (Pydantic BaseSettings)
│   │   ├── db/            # Async SQLAlchemy session
│   │   ├── models/        # ORM models (8 tables)
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── llm/           # LLM provider abstraction (Groq/Ollama)
│   │   ├── rag/           # Policy ingestion + pgvector retrieval
│   │   ├── security/      # PII detector + Injection detector
│   │   ├── risk/          # Deterministic risk scoring engine
│   │   ├── agents/        # Privacy, Security, Policy agents
│   │   ├── graph/         # LangGraph state + nodes + workflow
│   │   ├── audit/         # Immutable audit event logger
│   │   ├── repositories/  # Typed DB access (no arbitrary SQL)
│   │   ├── services/      # Business logic orchestration
│   │   ├── api/v1/        # FastAPI route handlers
│   │   └── main.py        # App factory + health endpoint
│   └── tests/             # pytest — deterministic components first
├── knowledge/
│   └── policies/          # 7 governance policy Markdown files
├── migrations/            # Alembic versions
├── scripts/
│   ├── ingest_policies.py # Load policies into pgvector
│   ├── seed_database.py   # Seed sample AI applications
│   └── run_demo.py        # Run all 5 demo scenarios
├── alembic.ini
├── pyproject.toml
└── .env.example
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager (`pip install uv`)
- PostgreSQL 14+ with pgvector extension
- Groq API key (free at [console.groq.com](https://console.groq.com)) _or_ Ollama installed locally

### 1. Clone and install

```bash
git clone <repo>
cd "AI compliance agent"
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values:
#   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ai_governance
#   GROQ_API_KEY=gsk_...
#   LLM_PROVIDER=groq
```

### 3. Create PostgreSQL database

```sql
-- In psql:
CREATE DATABASE ai_governance;
\c ai_governance
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4. Run migrations

```bash
uv run alembic upgrade head
```

### 5. Ingest governance policies

```bash
uv run python scripts/ingest_policies.py
```

### 6. Seed sample applications

```bash
uv run python scripts/seed_database.py
```

### 7. Start the API server

```bash
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
Health check: http://localhost:8000/health

---

## Demo Scenarios

Once Phase 4 (LangGraph) is complete, run all 5 governance scenarios:

```bash
uv run python scripts/run_demo.py
```

| Scenario | Description | Expected Decision |
|----------|-------------|------------------|
| 1 — Safe Application | Internal tool, no PII, approved model | LOW → **ALLOW** |
| 2 — PII Violation | Input contains email, phone, Aadhaar | HIGH → **REVIEW/BLOCK** |
| 3 — Prompt Injection | "Ignore previous instructions..." | CRITICAL → **BLOCK** |
| 4 — Exception | Policy violated but valid exception exists | Finding recorded, exception applied |
| 5 — Human Approval | High-risk but legitimate | **REVIEW** → Approval requested → Human approves → Audited |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + DB status |
| POST | `/api/v1/applications` | Register AI application |
| GET | `/api/v1/applications` | List applications |
| GET | `/api/v1/applications/{id}` | Get application |
| POST | `/api/v1/governance/evaluate` | **Main endpoint** — run governance evaluation |
| GET | `/api/v1/assessments/{id}` | Get assessment result |
| GET | `/api/v1/assessments/{id}/findings` | Get agent findings |
| GET | `/api/v1/approvals` | List approval requests |
| POST | `/api/v1/approvals/{id}/approve` | Human approves |
| POST | `/api/v1/approvals/{id}/reject` | Human rejects |
| POST | `/api/v1/approvals/exceptions` | Create policy exception |
| GET | `/api/v1/audit/events` | List audit events |
| POST | `/api/v1/audit/reports` | Generate governance report |

---

## Risk Scoring

```
Risk Dimensions (configurable weights):
  DATA_RISK        30%
  SECURITY_RISK    30%
  COMPLIANCE_RISK  20%
  MODEL_RISK       10%
  BUSINESS_IMPACT  10%

Score Thresholds → Decision:
   0–29   LOW      → ALLOW
  30–59   MEDIUM   → ALLOW (with monitoring)
  60–79   HIGH     → REVIEW (human approval required)
  80–100  CRITICAL → BLOCK (unless active exception)
```

---

## Environment Variables

See [`.env.example`](.env.example) for all configurable options.

---

## Development Phases

- [x] **Phase 1** — Project skeleton, config, DB models, migrations, health endpoint
- [x] **Phase 2** — Policy knowledge docs, RAG ingestion pipeline, pgvector retrieval
- [x] **Phase 3** — PII detector, Injection detector, 3 governance agents
- [x] **Phase 4** — LangGraph orchestration, Risk engine, Governance decisions
- [x] **Phase 5** — MCP tool server
- [x] **Phase 6** — Approval workflow, Exception management, Audit events
- [x] **Phase 7** — Audit reports, Demo scenarios
- [x] **Phase 8** — LangSmith observability
- [x] **Phase 9** — Streamlit dashboard

---

## Interview Talking Points

- **"Agents are responsible for reasoning over evidence, not for enforcing governance policy."**
- **"Governance decisions are deterministic and auditable; LLM reasoning is treated as one source of evidence."**
- **"The MCP layer provides a controlled capability boundary between agents and enterprise systems."**
- **"High-risk actions use human-in-the-loop approval rather than autonomous execution."**
- **"Expired exceptions cannot bypass violations — the is_currently_active check is authoritative."**

