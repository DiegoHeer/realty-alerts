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
- **Results:** persisted in Postgres via `django_celery_results` (`CELERY_RESULT_BACKEND = "django-db"`).
  Browse at <http://localhost:8000/admin/django_celery_results/taskresult/>.

Smoke-test from the api container (use `manage.py shell -c` so the Django app registry is ready before
the result backend is loaded):

```bash
docker compose -f docker-compose.dev.yml exec api python manage.py shell -c \
    "from scraping.tasks import ping; print(ping.delay().get(timeout=5))"
```

Watch the worker log:

```bash
docker compose -f docker-compose.dev.yml logs -f celery-worker
```

### Scheduling scrapes from the admin

`scraping.dispatch_scrape(website, run_id=None)` POSTs to the in-cluster Argo
Events webhook (`ARGO_EVENTS_WEBHOOK_URL`) which spawns a one-shot scraper
`Job`. To run a scrape on a schedule:

1. Open <http://localhost:8000/admin/django_celery_beat/periodictask/> (or the
   staging/production admin equivalent).
2. **Add periodic task** → name it `Scrape funda nightly` (or similar) → pick
   task `scraping.dispatch_scrape` from the dropdown.
3. Set kwargs:
   ```json
   {"website": "funda"}
   ```
   (Valid values: `funda`, `pararius`, `vastgoed_nl` — must match the
   `Website` enum in `scraping/models.py`. `run_id` is optional; the task
   generates a UUID when missing.)
4. Pick or create a Crontab schedule (e.g. `0 6 * * *` UTC).
5. Save. Beat will fire the task at the next matching tick; the worker POSTs
   to the webhook; Argo Events spawns the scrape Job.

If `ARGO_EVENTS_WEBHOOK_URL` is unset (local dev, preview namespaces), the
task short-circuits with a warning instead of erroring — useful for running
Beat locally without a real webhook to call.
