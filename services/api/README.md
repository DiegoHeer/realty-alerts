# api

Django 6.0 + Django Ninja backend. Django ORM over PostgreSQL (psycopg3), Gunicorn in production.

## Development

```bash
uv sync --dev
uv run python manage.py migrate
uv run python manage.py runserver  # :8000

uv run ruff check .
uv run ty check realty_api/ scraping/ tests/
uv run pytest tests/ -v
```

Settings split: `realty_api/settings/{base,local,prod,ci}.py` selected via `DJANGO_SETTINGS_MODULE`. See the repo-level [CLAUDE.md](../../CLAUDE.md) for the full Django + Django Ninja conventions.

The Docker image is `ghcr.io/diegoheer/realty-alerts/api` — built and pushed by [.github/workflows/api.yml](../../.github/workflows/api.yml). On merge to `main`, that workflow opens a `release/api-sha-…` PR on `realty-ai-platform` to promote the new image to production.
