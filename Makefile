.PHONY: dev fmt lint test seed up down ci

dev:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

fmt:
	black .

lint:
	ruff check .

test:
	pytest -q

seed:
	PYTHONPATH=. python -m scripts.seed_kb

up:
	docker compose -f compose.yaml up --build

down:
	docker compose -f compose.yaml down
