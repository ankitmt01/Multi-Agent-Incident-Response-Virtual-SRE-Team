Incident Copilot

AI-powered incident response console — detect, triage, validate, and execute remediation plans with guardrails.
Built with FastAPI, Retrieval-Augmented Generation (RAG), Docker, and Prometheus monitoring.

✨ Features

AI / RAG Knowledge Base

Uses Chroma vector database + sentence-transformer embeddings for semantic ingestion/retrieval of runbooks and past incidents

Retrieval-augmented generation (RAG) for suggesting remediation steps

Incident Workflow

Detector: flags incidents based on error rates and latency (configurable thresholds)

Policy Guard: enforces approval workflows, environment allowlists, safe deployment windows

Remediator & Validator: generates candidate plans, runs dry-runs, validates safety before live execution

Reporter: exports Markdown, HTML, and PDF reports

Secure & Controlled

Supports API Key (simple) and Scoped JWT (fine-grained RBAC) auth modes

Scopes: run, kb, audit, admin

Observability

Prometheus metrics (/metrics)

Real-time audit streaming (Server-Sent Events)

Web UI charts: incident timeline, severity breakdown, pipeline runs, approvals, executions, KB docs

Integrations

Slack notifications

JIRA ticket creation

Audit SSE for external log aggregation

UI Console

Single-page app with tabs for Overview, Incidents, Monitoring, KB, Audit, Reports, Settings

Charts, sparklines, and interactive drawers for candidates, executions, and live console logs

🛠️ Tech Stack

AI / NLP: sentence-transformers, Chroma vector DB

Backend: FastAPI, Pydantic, PyJWT

Frontend: Vanilla JS, HTML5, Canvas-based charts

DevOps: Docker Compose, Prometheus metrics, CI/CD ready

Integrations: Slack, JIRA

Export: Markdown, HTML, PDF (reportlab)

📦 Getting Started
Prerequisites

Docker & Docker Compose

Python 3.9+ (optional local run)

Clone & Run
git clone https://github.com/ankitmt01/Multi-Agent-Incident-Response-Virtual-SRE-Team.git
cd incident-copilot

# copy example env
cp .env.example .env

# start services
docker compose up --build




🔐 Authentication

API Key: Send X-API-Key in header

JWT: Send Authorization: Bearer <token> (scopes enforced)

UI has settings to store and switch between both modes.

📊 Monitoring

/metrics: Prometheus format

Charts in UI:

Incidents over time

Severity breakdown

Pipeline runs, approvals, executions, KB docs (sparklines)




📚 Skills Demonstrated

AI / RAG (vector DB, embeddings, semantic retrieval)

Cloud-Native (Docker Compose, modular microservices)

Backend (FastAPI, REST, JWT security)

DevOps / Policy Guardrails

Observability (Prometheus, SSE)

Frontend (JS, HTML5 dashboards)

Integrations (Slack, JIRA, PDF export)


.ENV
# -----------------------------
# Incident Copilot — Example .env
# -----------------------------

# ---- Core ----
PORT=8000
ENV_NAME=prod
ALLOWED_ORIGINS=*
LOG_LEVEL=info
STATE_DIR=state

# ---- Authentication ----
# Modes: api_key | scoped_jwt
AUTH_MODE=api_key
API_KEY=changeme-production

# Example for scoped keys (if AUTH_MODE=api_key)
# SCOPED_KEYS={"demo-key":["run","kb"],"auditor":["audit","admin"]}

# Example for JWT mode (if AUTH_MODE=scoped_jwt)
# JWT_SECRET=please-change
# JWT_AUDIENCE=incident-copilot
# JWT_ISSUER=https://auth.example.com

# ---- Vector DB (RAG Knowledge Base) ----
VECTOR_DB_DIR=/var/lib/chroma
COLLECTION_NAME=knowledge_base
CHROMA_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
KB_MIN_DOCS=1
RAG_TOP_K=5
RAG_MIN_SCORE=0.30

# ---- Detector thresholds ----
DETECT_ERR_HIGH=1.0
DETECT_ERR_MED=0.5
DETECT_P95_HIGH=1000
DETECT_P95_MED=800
DETECT_MIN_WINDOW_S=30

# ---- Policy guardrails ----
ENV_ALLOWLIST=dev,staging,prod
PROD_ENVS=prod,production
PEAK_START=09:00:00
PEAK_END=21:00:00
REQUIRE_APPROVAL_FOR_WRITES=1
BLOCK_GLOBAL_FF_IN_PROD=1
REQUIRE_BACKUP_FOR_SCHEMA=1
MAX_TARGETS_PROD=5
SENSITIVE_SERVICES=auth,payments

# ---- Integrations (optional) ----
SLACK_WEBHOOK_URL=
JIRA_BASE_URL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# ---- Telemetry (disabled by default) ----
POSTHOG_DISABLED=true
ANONYMIZED_TELEMETRY=false
CHROMADB_TELEMETRY_ENABLED=false
OTEL_SDK_DISABLED=true
CHROMA_TENANT=default_tenant
CHROMA_DATABASE=default_database
