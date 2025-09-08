.PHONY: help db-start db-stop db-reset dev install test lint clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	uv sync

db-start: ## Start PostgreSQL and Redis containers
	docker compose up -d postgres redis

db-stop: ## Stop database containers
	docker compose stop postgres redis

db-reset: ## Reset databases (WARNING: destroys all data)
	docker compose down -v postgres redis
	docker compose up -d postgres redis

dev: ## Start Django development server
	uv run python manage.py runserver

migrate: ## Apply database migrations
	uv run python manage.py migrate

makemigrations: ## Create database migrations
	uv run python manage.py makemigrations

shell: ## Open Django shell
	uv run python manage.py shell

worker: ## Start RQ worker for background tasks
	uv run python manage.py rqworker default

test: ## Run test suite
	uv run python manage.py test

lint: ## Run code linting
	@echo "Linting not configured yet - add flake8/black/ruff as needed"

clean: ## Clean Python cache and temp files
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

logs: ## View database container logs
	docker compose logs -f postgres redis

setup: install db-start migrate ## Complete initial setup
	@echo "Setup complete! Run 'make dev' to start the development server"