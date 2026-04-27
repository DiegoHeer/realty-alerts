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

## Background tasks (Celery + Beat)

`make dev` brings up Redis, a Celery worker, and Celery Beat alongside the api and database.

- **Worker:** runs `@shared_task` functions discovered under any installed app (e.g. `scraping.tasks`).
- **Beat:** uses `django_celery_beat.schedulers:DatabaseScheduler`, so periodic tasks live in Postgres
  and are managed at <http://localhost:8000/admin/django_celery_beat/periodictask/> after running
  `make api-superuser`.

Smoke-test from the api container:

```bash
docker compose -f docker-compose.dev.yml exec api \
    python -c "from scraping.tasks import ping; print(ping.delay().get(timeout=5))"
```

Watch the worker log:

```bash
docker compose -f docker-compose.dev.yml logs -f celery-worker
```
