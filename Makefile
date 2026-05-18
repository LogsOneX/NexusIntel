SHELL := /bin/sh

HOST ?= 127.0.0.1
PORT ?= 8080
SERVICE ?= nexusrecon
COMPOSE ?= $(shell if docker compose version >/dev/null 2>&1; then echo docker compose; elif command -v docker-compose >/dev/null 2>&1; then echo docker-compose; fi)

.PHONY: up down build logs restart ps shell install local doctor readiness

up:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found. Run ./start.sh for local fallback."; exit 1; fi
	mkdir -p results reports .nexusrecon
	NEXUS_HOST=$(HOST) NEXUS_PORT=$(PORT) $(COMPOSE) up -d --build
	@echo "NexusRecon dashboard: http://$(HOST):$(PORT)"

down:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	NEXUS_HOST=$(HOST) NEXUS_PORT=$(PORT) $(COMPOSE) down

build:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	NEXUS_HOST=$(HOST) NEXUS_PORT=$(PORT) $(COMPOSE) build

logs:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	$(COMPOSE) logs -f $(SERVICE)

restart:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	NEXUS_HOST=$(HOST) NEXUS_PORT=$(PORT) $(COMPOSE) restart $(SERVICE)

ps:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	$(COMPOSE) ps

shell:
	@if [ -z "$(COMPOSE)" ]; then echo "Docker Compose not found."; exit 1; fi
	$(COMPOSE) exec $(SERVICE) sh

install:
	python3 -m pip install -r requirements.txt

local:
	mkdir -p results reports .nexusrecon
	python3 main.py --no-banner dashboard $(HOST):$(PORT)

doctor:
	python3 main.py --no-banner doctor

readiness:
	python3 -c "from core.readiness import readiness_report; import json; print(json.dumps(readiness_report(), indent=2))"
