# Agentic AI – Multi-Agent Incident Response (Virtual SRE Team)

A virtual on-call SRE team made of **Agentic AI**: detects incidents, investigates with RAG, proposes fixes, validates them safely in a sandbox, and produces an explainable report.  
This repo is scaffolded for **Windows** first, with **Dockerized dev** for reproducibility.

---

## ✨ What’s here (scaffold only)
- **Agents (stubs):** Detector, Investigator (RAG), Remediator (tool-using), Validator (sandbox), Reporter
- **Adapters (stubs):** Metrics (Prometheus/OpenTelemetry), Git/PR, K8s/Sandbox, Policy Guard
- **KB:** seed runbooks/incidents + vector index folder
- **API/UI/Infra:** placeholders to plug in when you start building
- **Docs:** simple mermaid diagrams in `docs/`

> No business logic yet — this is the clean foundation to start coding and demoing fast.

---

## 🗂 Repo structure





---

## 💻 Prerequisites (Windows)

- **Git** → `git --version`  
- **Python 3.11+** → `python --version`  
- **Node.js 18+ / 20+** → `node --version` & `npm --version`  
- **VS Code** (recommended)  
- **Docker Desktop** with **WSL2 backend** (recommended for dev containers)

> For just creating the scaffold, Docker isn’t required. For containerized dev, install Docker Desktop and enable WSL2 in its settings.

---

## 🚀 Quick start (two ways)

### Option A — Local dev (no Docker yet)
1. **Backend venv**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
