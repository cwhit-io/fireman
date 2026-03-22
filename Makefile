.PHONY: help venv install env setup run dev worker tailwind test migrate makemigrations shell superuser wagtail-init collectstatic lint lint-fix format commit check clean reset pre-commit-install startapp docker-build docker-up docker-up-dev docker-down docker-logs docker-shell docker-manage stop reload

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

-include .env
export HOST ?= 0.0.0.0
export PORT ?= 8085

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create .venv if it does not exist
	test -d $(VENV) || python3 -m venv $(VENV)

install: venv ## Install all Python and Node dependencies
	$(PIP) install -r requirements.txt
	npm install

env: install ## Create .env from .env.example if missing, with a generated SECRET_KEY
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		SECRET=$$($(PYTHON) -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"); \
		sed -i "s/your-secret-key-here/$$SECRET/" .env; \
		echo "Created .env with a generated SECRET_KEY"; \
	else \
		echo ".env already exists, skipping"; \
	fi

pre-commit-install: install ## Install pre-commit hooks
	$(VENV)/bin/pre-commit install

setup: env pre-commit-install migrate collectstatic ## Bootstrap project from scratch (create .env, install deps, hooks, run migrations, collect static)

# ─── Production ────────────────────────────────────────────────────────────────

run: venv ## [PROD] Start Daphne + Celery (assets must already be built)
	@mkdir -p logs
	$(MAKE) -j2 _daphne _celery

_daphne:
	$(VENV)/bin/daphne -b $(HOST) -p $(PORT) config.asgi:application > logs/daphne.log 2>&1 & \
	echo $$! > logs/daphne.pid; \
	echo "Daphne started (PID $$(cat logs/daphne.pid))"

_celery:
	$(VENV)/bin/celery -A config worker -l info > logs/celery.log 2>&1 & \
	echo $$! > logs/celery.pid; \
	echo "Celery started (PID $$(cat logs/celery.pid))"

# ─── Development ───────────────────────────────────────────────────────────────

dev: venv ## [DEV] Build assets, then start Daphne + Celery + Tailwind watch
	@mkdir -p logs
	@echo "Building assets..."
	npm run tailwind:build
	$(PYTHON) manage.py collectstatic --noinput
	$(MAKE) -j3 _daphne _celery _tailwind

_tailwind:
	npm run tailwind:watch > logs/tailwind.log 2>&1 & \
	NPM_PID=$$!; \
	sleep 1; \
	NODE_PID=$$(pgrep -P $$NPM_PID 2>/dev/null | head -1); \
	if [ -n "$$NODE_PID" ]; then \
		echo $$NODE_PID > logs/tailwind.pid; \
		echo "Tailwind started (node PID $$NODE_PID, npm PID $$NPM_PID)"; \
	else \
		echo $$NPM_PID > logs/tailwind.pid; \
		echo "Tailwind started (PID $$NPM_PID)"; \
	fi

# ─── Stop / Reload ─────────────────────────────────────────────────────────────

stop: ## Stop all running services
	@echo "Stopping services..."

	@# Daphne
	@if [ -f logs/daphne.pid ]; then \
		PID=$$(cat logs/daphne.pid); \
		if ps -p $$PID -o comm= 2>/dev/null | grep -q "daphne"; then \
			kill $$PID 2>/dev/null && echo "Daphne stopped (PID $$PID)" || true; \
		else \
			echo "Daphne not running (stale PID $$PID)"; \
		fi; \
		rm -f logs/daphne.pid; \
	else \
		pgrep -f "daphne -b $(HOST) -p $(PORT)" | xargs -r kill 2>/dev/null || true; \
	fi

	@# Celery
	@if [ -f logs/celery.pid ]; then \
		PID=$$(cat logs/celery.pid); \
		if ps -p $$PID -o comm= 2>/dev/null | grep -q "celery"; then \
			kill $$PID 2>/dev/null && echo "Celery stopped (PID $$PID)" || true; \
		else \
			echo "Celery not running (stale PID $$PID)"; \
		fi; \
		rm -f logs/celery.pid; \
	else \
		pgrep -f "celery -A config worker" | xargs -r kill 2>/dev/null || true; \
	fi

	@# Tailwind — PID only, no pgrep fallback
	@if [ -f logs/tailwind.pid ]; then \
		PID=$$(cat logs/tailwind.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			kill $$PID 2>/dev/null && echo "Tailwind stopped (PID $$PID)" || true; \
		else \
			echo "Tailwind not running (stale PID $$PID)"; \
		fi; \
		rm -f logs/tailwind.pid; \
	fi

	@echo "Stopped."

reload: stop run ## Restart production services
	@echo "Reloaded."

reload-dev: stop dev ## Restart dev services (rebuilds assets)
	@echo "Reloaded (dev)."

# ─── Django ────────────────────────────────────────────────────────────────────

test: venv ## Run tests with pytest + coverage report
	$(VENV)/bin/pytest

lint: venv ## Lint code with ruff
	$(VENV)/bin/ruff check .

lint-fix: venv ## Lint and auto-fix with ruff
	$(VENV)/bin/ruff check . --fix

format: venv ## Auto-format code with ruff
	$(VENV)/bin/ruff format .

commit: venv ## Format, fix, stage everything, then commit (usage: make commit m="message")
	@[ "$(m)" ] || (echo "Usage: make commit m=\"your message\""; exit 1)
	$(VENV)/bin/ruff check --fix .
	$(VENV)/bin/ruff format .
	git add -A
	git commit -m "$(m)"

migrate: venv ## Apply database migrations
	$(PYTHON) manage.py migrate

makemigrations: venv ## Create new migrations
	$(PYTHON) manage.py makemigrations

shell: venv ## Open Django shell
	$(PYTHON) manage.py shell

superuser: venv ## Create a superuser
	$(PYTHON) manage.py createsuperuser

collectstatic: venv ## Collect static files
	$(PYTHON) manage.py collectstatic --noinput

check: venv ## Run Django deployment checks
	$(PYTHON) manage.py check --deploy

startapp: venv ## Scaffold a new app in apps/ (usage: make startapp name=myapp)
	@[ "$(name)" ] || (echo "Usage: make startapp name=<appname>"; exit 1)
	mkdir -p apps/$(name)
	$(PYTHON) manage.py startapp $(name) apps/$(name)
	@sed -i "s/name = '$(name)'/name = 'apps.$(name)'/" apps/$(name)/apps.py
	@echo ""
	@echo "App created at apps/$(name)/"
	@echo "Add 'apps.$(name)' to INSTALLED_APPS in config/settings/base.py"

# ─── Maintenance ───────────────────────────────────────────────────────────────

clean: ## Remove cache files, compiled Python, and the SQLite database
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f db.sqlite3

reset: clean setup ## Full teardown and rebuild (clean + setup)

# ─── Docker ────────────────────────────────────────────────────────────────────

docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start all Docker services (detached)
	docker compose up -d

docker-up-dev: ## Start Docker services + Tailwind watch (detached)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

docker-down: ## Stop and remove Docker containers
	docker compose down

docker-logs: ## Tail logs for all Docker services
	docker compose logs -f

docker-shell: ## Open a shell in the web container
	docker compose exec web bash

docker-manage: ## Run a manage.py command in the web container (usage: make docker-manage cmd="migrate")
	docker compose exec web python manage.py $(cmd)

# ─── Assets ────────────────────────────────────────────────────────────────────

organize-assets: ## Create assets/printer layout and copy barcodes, fonts, and PPD (no overwrite)
	@echo "Creating assets/printer layout..."
	mkdir -p assets/printer/barcodes assets/printer/fonts/trueType assets/printer/ppd
	cp -n barcodes/*.tif assets/printer/barcodes/ 2>/dev/null || true
	cp -n fonts/usps/trueType/*.ttf assets/printer/fonts/trueType/ 2>/dev/null || true
	cp -n EF678921.PPD assets/printer/ppd/ 2>/dev/null || true
	@echo "assets/printer prepared (existing files preserved)."
