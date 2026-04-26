.PHONY: help dev scraper api api-migrate api-superuser api-shell mobile web pre-commit lint format typecheck test build build-scraper build-api build-web

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

mobile: ## Start Expo dev server
	cd apps/mobile && npx expo start

web: ## Start Next.js dev server
	cd apps/web && npm run dev

# --- Quality ---

pre-commit: ## Run all pre-commit checks
	pre-commit run --all-files

lint: ## Lint all Python services
	cd services/scraper && uv run ruff check src/ tests/
	cd services/api && uv run ruff check realty_api/ scraping/ tests/

format: ## Format all Python services
	cd services/scraper && uv run ruff format src/ tests/
	cd services/api && uv run ruff format realty_api/ scraping/ tests/

typecheck: ## Typecheck all Python services
	cd services/scraper && uv run ty check src/ tests/
	cd services/api && uv run ty check realty_api/ scraping/ tests/

test: ## Run all tests
	cd services/scraper && uv run pytest tests/
	cd services/api && uv run pytest tests/
	cd apps/mobile && npm test
	cd apps/web && npm test

# --- Build ---

build-scraper: ## Build scraper Docker image
	docker build -t ghcr.io/diegoheer/realty-alerts/scraper:latest services/scraper

build-api: ## Build API Docker image
	docker build -t ghcr.io/diegoheer/realty-alerts/api:latest services/api

build-web: ## Build landing page Docker image
	docker build -t ghcr.io/diegoheer/realty-alerts/web:latest apps/web

build: build-scraper build-api build-web ## Build all Docker images
