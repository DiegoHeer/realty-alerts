# CLAUDE.md

## Rules

- **Ask before acting:** Only start executing when you have at least 95% confidence on the topic. Otherwise, ask clarifying questions, reason through the problem, or do web research for more context.
- **PR preflight:** Before creating a PR, always run all relevant tests (`make test`) and pre-commit checks (`make pre-commit`) and fix any failures first.
- **Conventional Commits:** every commit follows [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/). See `## Commits`.
- **Atomic commits:** one logical change per commit, summarisable in a single sentence. See `## Commits`.

## Commits

All commits follow [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) and must be atomic.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

- `<description>` is imperative mood, lowercase, no trailing period, ≤ 72 chars.
- Body (when needed) explains the *why*, not the *what*. One blank line after the description.
- Footers use `Token: value` form (e.g. `Refs: #123`, `Co-Authored-By: ...`).

### Allowed types

| Type | Use for |
|---|---|
| `feat` | new user-visible functionality (MINOR bump) |
| `fix` | bug fix (PATCH bump) |
| `docs` | documentation only |
| `style` | formatting, whitespace, lint-only changes (no logic) |
| `refactor` | internal restructuring with no behaviour change |
| `perf` | performance improvement |
| `test` | adding or updating tests only |
| `build` | build system, Docker, dependencies (`uv`, `npm`) |
| `ci` | GitHub Actions, pre-commit config |
| `chore` | maintenance that does not fit above (rare) |
| `revert` | revert a previous commit |

### Allowed scopes

Scope is **required** and must be one of: `api`, `scraper`, `mobile`, `web`, `docker`, `ci`, `deps`, `repo`.

- Use `repo` for cross-cutting changes (root configs, Makefile, top-level docs).
- Use `deps` for dependency bumps that span services; otherwise scope to the service (`feat(api): ...`).

### Breaking changes

Breaking changes **must** use both signals:

1. Append `!` before the colon: `feat(api)!: ...`
2. Include a `BREAKING CHANGE:` footer explaining the break and the migration.

Example:

```
feat(api)!: drop legacy /v1 listings endpoint

BREAKING CHANGE: clients must migrate to /v2/listings. The /v1 route
now returns 410 Gone. Mobile app ≥ 1.4 already uses /v2.
```

### Atomic commits

Each commit does **one** thing, summarisable in a single sentence:

- One logical change. Don't mix a refactor with a feature, or formatting with logic.
- The repo must build and tests must pass at every commit (bisectable history).
- If `git diff --stat` touches unrelated areas, split with `git add -p` or `git restore --staged`.
- Pure formatting/rename commits go in their own `style:` or `refactor:` commit, separate from behaviour changes.
- A commit that needs the word "and" in its description is probably two commits.

### Examples

Good:

- `feat(scraper): add Funda fetch strategy`
- `fix(api): handle null price in ListingRead`
- `refactor(mobile): extract useListingFilters hook`
- `build(deps): bump expo from 52.0.0 to 52.0.7`
- `docs(repo): document conventional commits in CLAUDE.md`
- `ci(repo): run mobile jest only on apps/mobile changes`
- `test(scraper): cover VastgoedNL pagination edge case`

Bad (and why):

- `API|Migrate: replace FastAPI...` — legacy format, not Conventional Commits.
- `feat(api): add endpoint and fix unrelated bug` — two changes, split it.
- `chore: stuff` — no scope, no real description.
- `Update files` — not a Conventional Commit at all.

## Project Overview

Realty Alerts — real estate listing notifications for the Dutch housing market. Monorepo holding application code only; deployment is GitOps via [realty-ai-platform](https://github.com/DiegoHeer/realty-ai-platform) (Talos + k3s + ArgoCD).

## Repository Structure

```
services/scraper/   Python CDC scraper (BeautifulSoup, Playwright, httpx)
services/api/       FastAPI backend (SQLModel, Alembic, asyncpg)
apps/mobile/        React Native / Expo (TanStack Query, Zustand, NativeWind)
apps/web/           Next.js 15 static landing page (Tailwind CSS)
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
- Mobile: Expo 52, React Native 0.76, Expo Router, Zod for validation
- Web: Next.js 15, React 19, Tailwind CSS 4, Framer Motion

## SQLModel & Alembic Conventions (services/api)

- SQLModel table models: use `table=True`, `Field()` for columns, Python type hints for nullability
- Separate schemas from table models: `FooCreate` / `FooRead` / `FooUpdate` as plain SQLModel (no `table=True`)
- Relationships: use `Relationship()` with `back_populates`, `sa_relationship_kwargs` for cascade/lazy loading
- Many-to-many: explicit link table model with `table=True` and composite primary key
- Prefer `select()` + `session.exec()` over legacy `session.query()`
- Eager loading: use `selectinload()` / `joinedload()` to avoid N+1 queries
- Alembic migrations:
  - One logical change per migration (don't mix schema changes with data migrations)
  - Always review autogenerated migrations before applying (`alembic revision --autogenerate -m "description"`)
  - Test both upgrade and downgrade paths
  - For zero-downtime: add columns as nullable first, backfill, then add constraints in a follow-up migration
  - Never drop columns in the same release that stops writing to them

## Architecture Decisions

- Scraper is CDC-style (scrape all new listings since last run), API matches listings to user filters
- Scraper architecture: Protocol + Strategy pattern (FetchStrategy + Scraper protocols)
- Notifications: Expo Push (FCM/APNs)
- Database: standalone PostgreSQL, no separate search engine
- Authentication: not yet wired (`get_current_user` returns 501); replacement provider lands in a follow-up PR
- Shared code: duplicate small files across services (no shared package)
- Deployment: GitOps via [realty-ai-platform](https://github.com/DiegoHeer/realty-ai-platform) — this repo only builds and pushes images
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

## Installed Skills

Skills live in `.claude/skills/` and are auto-loaded by Claude Code. Use the right skill for the service you're working on.

### Scraper (`services/scraper/`)

| Skill | When to use |
|---|---|
| `web-scraping` | Anti-bot bypass, scraping cascades, content extraction, rate limiting, poison pill detection |
| `pydantic` | Pydantic v2 models, validators, BaseSettings, serialization |
| `pytest` | Writing/refactoring tests, fixtures, parametrize, mocking, async testing |

### API (`services/api/`)

| Skill | When to use |
|---|---|
| `fastapi` | Endpoints, dependencies, middleware, `Annotated` params, async vs sync decisions (official FastAPI skill) |
| `pydantic` | Request/response schemas, validation, BaseSettings |
| `pytest` | Test fixtures, FastAPI TestClient, pytest-asyncio patterns, factory-boy |

### Mobile (`apps/mobile/`)

| Skill | When to use |
|---|---|
| `react-native` | RN 0.76+ / Expo 52+ breaking changes, New Architecture, React 19 migration pitfalls |
| `zustand` | Store patterns, `useShallow`, persist middleware, TypeScript `create<T>()()` pattern, client vs server state separation |
| `frontend-design` | UI components, screens, polished design — use for any visual work (official Anthropic skill) |

### Web (`apps/web/`)

| Skill | When to use |
|---|---|
| `tailwindcss-fundamentals-v4` | Tailwind v4 syntax: `@theme` directive, OKLCH colors, `@utility`, CSS-first config (not v3 `tailwind.config.js`) |
| `framer-motion-animator` | Entrance/exit animations, scroll-triggered effects, page transitions, `useReducedMotion` |
| `frontend-design` | Landing page components, layout, visual polish (official Anthropic skill) |
