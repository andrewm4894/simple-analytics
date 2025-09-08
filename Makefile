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

# Code Quality Commands
format: ## Format code with black and ruff
	uv run ruff format .
	uv run black .
	uv run isort .

lint: ## Run all linting checks
	uv run ruff check .
	uv run mypy .
	uv run bandit -c pyproject.toml -r .

lint-fix: ## Run linting with auto-fixes
	uv run ruff check --fix .
	uv run isort .
	uv run black .

security: ## Run security checks
	uv run bandit -c pyproject.toml -r .
	uv run safety check

type-check: ## Run type checking
	uv run mypy .

check-all: lint security ## Run all code quality checks

# Pre-commit Commands
pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run: ## Run pre-commit on all files
	uv run pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	uv run pre-commit autoupdate

clean: ## Clean Python cache and temp files
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -name ".mypy_cache" -exec rm -rf {} +
	find . -name ".ruff_cache" -exec rm -rf {} +

logs: ## View database container logs
	docker compose logs -f postgres redis

setup: install db-start migrate pre-commit-install ## Complete initial setup
	@echo "Setup complete!"
	@echo "Run 'make dev' to start the development server"
	@echo "Run 'make check-all' to verify code quality"
