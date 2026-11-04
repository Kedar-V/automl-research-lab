COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: ensure-env up down logs test install health venv demo-sse rebuild-gateway frontend start airflow

ensure-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

# One command: Docker stack + Vite UI (blocks on npm run dev).
start: ensure-env
	$(COMPOSE) up --build -d
	@echo "Waiting for gateway on :8000..."
	@i=0; while [ $$i -lt 36 ]; do \
	  if curl -sf http://127.0.0.1:8000/healthz >/dev/null; then echo "gateway ok"; break; fi; \
	  i=$$((i+1)); sleep 5; \
	  if [ $$i -eq 36 ]; then echo "gateway not ready — try: make health / make logs"; exit 1; fi; \
	done
	@echo "Open http://127.0.0.1:5173  (Ctrl+C stops Vite; stack stays up — make down to stop Docker)"
	cd frontend && npm install && npm run dev

frontend:
	cd frontend && npm run dev

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -e ".[dev]"

up: ensure-env
	$(COMPOSE) up --build -d
	@echo "Waiting for service health..."
	@$(COMPOSE) ps

airflow: ensure-env
	$(COMPOSE) --profile airflow up --build -d
	@echo "Airflow starting (often 1–2 min). Check: $(COMPOSE) --profile airflow ps"
	@echo "UI: http://localhost:8088  (admin / admin unless .env overrides)"

down: ensure-env
	$(COMPOSE) --profile airflow down

logs: ensure-env
	$(COMPOSE) logs -f --tail=100

test: install
	$(PYTHON) -m pytest tests/contract -q

rebuild-gateway: ensure-env
	$(COMPOSE) up --build -d gateway

health:
	@for port in 8000 8011 8002 8003 8004 8005 8006; do \
	  printf "localhost:%s -> " "$$port"; \
	  curl -sf "http://127.0.0.1:$$port/healthz" || printf "FAIL"; \
	  printf "\n"; \
	done

# Stage A1: create a mock session and stream SSE until done.
# Usage: make demo-sse SCENARIO=happy
SCENARIO ?= happy
demo-sse:
	@SID=$$(curl -sf -X POST http://127.0.0.1:8000/sessions \
	  -H 'Content-Type: application/json' \
	  -d '{"target_column":"churned","scenario":"$(SCENARIO)"}' | $(PYTHON) -c 'import sys,json; print(json.load(sys.stdin)["session_id"])'); \
	echo "session=$$SID scenario=$(SCENARIO)"; \
	curl -sf -N "http://127.0.0.1:8000/sessions/$$SID/events"
