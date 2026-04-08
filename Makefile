.PHONY: help dev scraper-dev api-dev mobile-dev web-dev lint test build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Local Development ---

dev: ## Start all services locally via docker-compose
	docker compose -f docker-compose.dev.yml up --build

scraper-dev: ## Run scraper locally
	cd services/scraper && uv run python -m scraper

api-dev: ## Run API locally
	cd services/api && uv run uvicorn app.main:create_app --factory --reload --port 8000

mobile-dev: ## Start Expo dev server
	cd apps/mobile && npx expo start

web-dev: ## Start Next.js dev server
	cd apps/web && npm run dev

# --- Quality ---

pre-commit: ## Run all pre-commit checks
	pre-commit run --all-files

lint: ## Lint all Python services
	cd services/scraper && uv run ruff check src/ tests/
	cd services/api && uv run ruff check src/ tests/

format: ## Format all Python services
	cd services/scraper && uv run ruff format src/ tests/
	cd services/api && uv run ruff format src/ tests/

test: ## Run all tests
	cd services/scraper && uv run pytest tests/
	cd services/api && uv run pytest tests/
	cd apps/mobile && npm test

# --- Build ---

build-scraper: ## Build scraper Docker image
	docker build -t ghcr.io/diegoheer/realty-scraper:latest services/scraper

build-api: ## Build API Docker image
	docker build -t ghcr.io/diegoheer/realty-api:latest services/api

build-web: ## Build landing page Docker image
	docker build -t ghcr.io/diegoheer/realty-web:latest apps/web

build: build-scraper build-api build-web ## Build all Docker images

# --- Infrastructure ---

tf-plan-dev: ## Terraform plan for dev
	cd infra/terraform && terraform plan -var-file=dev.tfvars

tf-plan-prod: ## Terraform plan for prod
	cd infra/terraform && terraform plan -var-file=prod.tfvars

tf-apply-dev: ## Terraform apply for dev
	cd infra/terraform && terraform apply -var-file=dev.tfvars

tf-apply-prod: ## Terraform apply for prod
	cd infra/terraform && terraform apply -var-file=prod.tfvars
