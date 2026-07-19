.PHONY: help dev scraper api api-migrate api-superuser api-shell pre-commit lint format typecheck test build build-scraper build-api

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Local Development ---

dev: ## Start all services locally via docker-compose
	docker compose -f docker-compose.dev.yml up --build

scraper: ## Run scraper locally
	cd services/scraper && uv run python -m scraper

api: ## Run API locally (Django runserver, sqlite by default)
	cd services/api && uv run python manage.py runserver 0.0.0.0:8000

api-migrate: ## Apply Django migrations locally
	cd services/api && uv run python manage.py migrate

api-superuser: ## Create a Django admin superuser locally
	cd services/api && uv run python manage.py createsuperuser

api-shell: ## Open a Django shell locally
	cd services/api && uv run python manage.py shell

# --- Quality ---

pre-commit: ## Run all pre-commit checks
	pre-commit run --all-files

lint: ## Lint all Python services
	cd services/scraper && uv run ruff check src/ tests/
	cd services/api && uv run ruff check realty_api/ scraping/ accounts/ tests/

format: ## Format all Python services
	cd services/scraper && uv run ruff format src/ tests/
	cd services/api && uv run ruff format realty_api/ scraping/ accounts/ tests/

typecheck: ## Typecheck all Python services
	cd services/scraper && uv run ty check src/ tests/
	cd services/api && uv run ty check realty_api/ scraping/ accounts/ tests/

test: ## Run all tests
	cd services/scraper && uv run pytest tests/
	cd services/api && uv run pytest tests/

# --- Build ---

build-scraper: ## Build scraper Docker image
	docker build -t ghcr.io/diegoheer/realty-alerts/scraper:latest services/scraper

build-api: ## Build API Docker image
	docker build -t ghcr.io/diegoheer/realty-alerts/api:latest services/api

build: build-scraper build-api ## Build all Docker images
