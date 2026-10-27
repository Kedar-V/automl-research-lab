COMPOSE := docker compose -f infra/docker-compose.yml
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: up down logs test install health venv demo-sse rebuild-gateway frontend

frontend:
	cd frontend && npm run dev

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -e ".[dev]"

up:
	$(COMPOSE) up --build -d
	@echo "Waiting for service health..."
	@$(COMPOSE) ps

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

test: install
	$(PYTHON) -m pytest tests/contract -q

rebuild-gateway:
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
