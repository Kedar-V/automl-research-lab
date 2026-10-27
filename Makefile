COMPOSE := docker compose -f infra/docker-compose.yml
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: up down logs test install health venv

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

health:
	@for port in 8000 8011 8002 8003 8004 8005 8006; do \
	  printf "localhost:%s -> " "$$port"; \
	  curl -sf "http://127.0.0.1:$$port/healthz" || printf "FAIL"; \
	  printf "\n"; \
	done
