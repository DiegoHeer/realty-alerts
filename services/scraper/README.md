# scraper

CDC scraper for Dutch real-estate listings. Runs as a one-shot job that fetches new listings since the last run and writes them to the api's database. Built around a Protocol + Strategy pattern (`FetchStrategy` + `Scraper`).

## Development

```bash
uv sync --dev
uv run python -m scraper

uv run ruff check src/ tests/
uv run ty check src/ tests/
uv run pytest tests/ -v
```

Connects to a remote Playwright server at `$BROWSER_URL` (the image deliberately doesn't bundle browsers). See the repo-level [CLAUDE.md](../../CLAUDE.md) for project-wide conventions.

The Docker image is `ghcr.io/diegoheer/realty-alerts/scraper` — built and pushed by [.github/workflows/scraper.yml](../../.github/workflows/scraper.yml). Deployed as a Kubernetes CronJob (no preview env, no HTTP surface).
