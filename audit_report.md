# Repo Audit Report

**Coverage score:** 58.3%  
_Total heuristics satisfied vs. spec features_

## Checks
- OK **FastAPI app present**  
  Files: backend\app\main.py, backend\app\api\main.py
- OK **Pydantic Incident model**  
  Files: backend\app\models\incident.py, backend\app\repositories\incidents.py, backend\app\services\incidents_service.py, backend\app\api\routers\demo.py, backend\app\api\routers\incidents.py
- X **Agents framework (LangGraph/AutoGen/CrewAI)**  
  Files: -
- OK **Detector agent**  
  Files: backend\app\agents\detector.py, backend\app\services\pipeline.py
- OK **Investigator agent**  
  Files: backend\app\agents\investigator.py, backend\app\services\pipeline.py
- OK **Remediator agent**  
  Files: backend\app\agents\remediator.py, backend\app\services\pipeline.py
- OK **Validator agent**  
  Files: backend\app\agents\validator.py, backend\app\services\pipeline.py, backend\app\api\routers\debug.py
- OK **Reporter agent**  
  Files: backend\app\agents\reporter.py, backend\app\services\pipeline.py
- OK **RAG components (Vector DB)**  
  Files: backend\app\adapters\vectorstore.py, backend\app\agents\vectorstore.py, backend\app\services\rag.py
- X **Git/CI integration**  
  Files: -
- X **Kubernetes API usage**  
  Files: -
- X **Prometheus/OpenTelemetry adapters**  
  Files: -
- OK **Policy engine (OPA-style)**  
  Files: audit_report.json, .git\index, .git\hooks\update.sample, ui\src\App.jsx, ui\src\DemoPanel.jsx
- X **Slack integration**  
  Files: -
- X **Jira integration**  
  Files: -
- OK **Dockerfile present**  
  Files: backend\Dockerfile, ui\Dockerfile
- OK **Docker Compose**  
  Files: infra\docker-compose.yml
- OK **Smoke tests present**  
  Files: backend\app\agents\remediator.py, backend\app\scripts\seed_kb.py
- X **WebSockets/live trace**  
  Files: -
- OK **UI (React)**  
  Files: ui\package.json
- OK **UI (Vue)**  
  Files: ui\package.json
- X **Graph libs (networkx/igraph)**  
  Files: -
- X **Forecasting (prophet/statsmodels/torch)**  
  Files: -
- X **Plotting (plotly/chart.js)**  
  Files: -