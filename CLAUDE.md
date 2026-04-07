# CLAUDE.md

## Rules

- **Ask before acting:** Only start executing when you have at least 95% confidence on the topic. Otherwise, ask clarifying questions, reason through the problem, or do web research for more context.
- **PR preflight:** Before creating a PR, always run all relevant tests (`make test`) and pre-commit checks (`make pre-commit`) and fix any failures first.

## Project Overview

Realty Alerts — real estate listing notifications for the Dutch housing market. Monorepo with 5 services deployed on self-hosted Proxmox + k3s.

## Repository Structure

```
services/scraper/   Python CDC scraper (BeautifulSoup, Playwright, httpx)
services/api/       FastAPI backend (SQLModel, Alembic, asyncpg, Supabase Auth)
apps/mobile/        React Native / Expo (TanStack Query, Zustand, NativeWind)
apps/web/           Next.js 15 static landing page (Tailwind CSS)
infra/terraform/    Proxmox VMs, k3s, K8s resources, Supabase, monitoring
```

## Development Commands

```bash
make dev              # docker-compose up all services
make pre-commit       # run all pre-commit checks
make lint             # ruff check both Python services
make format           # ruff format both Python services
make test             # pytest (scraper + api) + jest (mobile)
make build            # build all Docker images

# Per-service
make scraper-dev      # run scraper locally
make api-dev          # uvicorn with --reload on :8000
make mobile-dev       # expo start
make web-dev          # next dev
```

## Python Conventions (services/scraper, services/api)

- Python 3.12+, managed with `uv`
- Ruff linter + formatter, line length 120
- Modern Python: f-strings, `list[X]` (not `List[X]`), `StrEnum`, walrus operator, absolute imports only
- Type hints everywhere, Pydantic `BaseModel`/`BaseSettings` for data and config
- `loguru` for logging (not stdlib `logging`)
- Minimal docstrings — code should be self-documenting
- Leading underscore for private helpers, ALL_CAPS for constants
- Fully synchronous — Celery for background work
- Tests: pytest + pytest-mock + factory-boy (api uses pytest-asyncio with `asyncio_mode="auto"`)
- Pre-commit hooks: ruff check + ruff format per service, trailing whitespace, YAML/TOML checks

## Frontend Conventions (apps/mobile, apps/web)

- TypeScript throughout
- Mobile: Expo 52, React Native 0.76, Expo Router, Supabase JS, Zod for validation
- Web: Next.js 15, React 19, Tailwind CSS 4, Framer Motion

## Architecture Decisions

- Scraper is CDC-style (scrape all new listings since last run), API matches listings to user filters
- Scraper architecture: Protocol + Strategy pattern (FetchStrategy + Scraper protocols)
- Notifications: Expo Push (FCM/APNs)
- Real-time: Supabase Realtime (Postgres change subscriptions)
- Database: PostgreSQL via Supabase, no separate search engine
- Shared code: duplicate small files across services (no shared package)
- Terraform: single config with dev.tfvars / prod.tfvars + workspaces
- CI: GitHub Actions with per-service path-filtered workflows

## Testing

```bash
# Scraper
cd services/scraper && uv run pytest tests/ -v

# API (needs PostgreSQL — use docker-compose.dev.yml)
cd services/api && uv run pytest tests/ -v

# Mobile
cd apps/mobile && npm test
```

## Docker

```bash
docker compose -f docker-compose.dev.yml up -d   # PostgreSQL + Playwright
make build-scraper    # ghcr.io/diegoheer/realty-scraper:latest
make build-api        # ghcr.io/diegoheer/realty-api:latest
make build-web        # ghcr.io/diegoheer/realty-web:latest
```
