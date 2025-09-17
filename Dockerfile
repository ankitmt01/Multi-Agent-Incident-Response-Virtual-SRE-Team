# -------- Base build stage --------
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

# -------- Dependency stage --------
FROM base AS deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# -------- Runtime stage --------
FROM base AS runtime
RUN useradd -u 10001 -m appuser
COPY --from=deps /usr/local /usr/local
COPY . /app
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "-lc", "uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
