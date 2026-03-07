.PHONY: help venv install env setup run dev worker tailwind test migrate makemigrations shell superuser wagtail-init collectstatic lint lint-fix format commit check clean reset pre-commit-install startapp docker-build docker-up docker-up-dev docker-down docker-logs docker-shell docker-manage

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

setup: env pre-commit-install migrate wagtail-init collectstatic ## Bootstrap project from scratch (create .env, install deps, hooks, run migrations, init Wagtail, collect static)

run: venv ## Start Daphne, Celery worker, and Tailwind in parallel
	$(MAKE) -j3 dev worker tailwind

dev: venv ## Start Daphne ASGI server
	$(VENV)/bin/daphne -b $(HOST) -p $(PORT) config.asgi:application

worker: venv ## Start Celery worker
	$(VENV)/bin/celery -A config worker -l info

tailwind: ## Watch and rebuild Tailwind CSS
	npm run tailwind:watch

test: venv ## Run tests with pytest + coverage report
	$(VENV)/bin/pytest

lint: venv ## Lint code with ruff
	$(VENV)/bin/ruff check .

lint-fix: venv ## Lint code with ruff
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

wagtail-init: venv ## Bootstrap Wagtail with default Site and HomePage
	$(PYTHON) manage.py bootstrap_wagtail

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

clean: ## Remove cache files, compiled Python, and the SQLite database
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f db.sqlite3

reset: clean setup ## Full teardown and rebuild (clean + setup)

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
