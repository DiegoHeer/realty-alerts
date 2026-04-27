# Celery + Beat + Redis Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Celery + Celery Beat + Redis into the Django+Ninja API service with `django-celery-beat`'s DatabaseScheduler, and ship matching Kubernetes manifests in `realty-ai-platform` so admins can later manage scrape schedules through the Django admin.

**Architecture:** Same image runs three Django roles via different `command:` entries — gunicorn (web), `celery worker`, `celery beat`. Beat uses `django_celery_beat.schedulers:DatabaseScheduler` so schedules live in Postgres and are editable from `/admin/django_celery_beat/periodictask/`. Redis (auth-required, AOF on) is a sibling Kustomize app, ArgoCD-synced one wave before the api app.

**Tech Stack:** Python 3.14, Django 6.0, `celery[redis]>=5.5`, `django-celery-beat>=2.7`, `redis>=5.2` (Python client), Redis 8 (server), Kustomize, ArgoCD, KSOPS+Age for secrets.

**Approved spec:** `/home/diego/.claude/plans/previously-on-v1-0-0-of-mutable-kurzweil.md`

**Repos touched:**
- `realty-alerts` (this repo) — Phase 1 (Tasks 1–9).
- `realty-ai-platform` at `/home/diego/projects/realty-ai-platform` — Phase 2 (Tasks 10–16).
- Cross-repo PR & merge ordering — Phase 3 (Task 17).

---

## Phase 1 — API service: Celery wiring

### Task 1: Add Celery dependencies

**Files:**
- Modify: `services/api/pyproject.toml`
- Modify: `services/api/uv.lock` (regenerated)

- [ ] **Step 1: Add deps to pyproject.toml**

In `services/api/pyproject.toml`, add the three new packages to the `[project] dependencies` array (preserve alphabetical ordering as much as the existing list does):

```toml
dependencies = [
    "celery[redis]>=5.5",
    "dj-database-url>=2.3",
    "django>=6.0.4",
    "django-celery-beat>=2.7",
    "django-ninja>=1.6",
    "gunicorn>=23",
    "loguru>=0.7",
    "psycopg[binary]>=3.3",
    "pydantic-settings>=2.9",
    "redis>=5.2",
    "secret-key-generator>=0.0.8",
    "whitenoise>=6.8",
]
```

- [ ] **Step 2: Sync the lockfile**

Run from repo root:
```bash
cd services/api && uv sync
```
Expected: `uv` installs the three new packages plus their transitive deps (`amqp`, `kombu`, `vine`, `billiard`, `python-crontab`, `tzdata`, `cron-descriptor`).

- [ ] **Step 3: Verify imports work**

```bash
cd services/api && uv run python -c "import celery, django_celery_beat, redis; print(celery.__version__)"
```
Expected: prints a version string ≥ `5.5`.

- [ ] **Step 4: Commit**

```bash
git add services/api/pyproject.toml services/api/uv.lock
git commit -m "build(api): add celery, django-celery-beat, redis deps"
```

---

### Task 2: Extend `Settings` with Celery env vars

**Files:**
- Modify: `services/api/realty_api/env.py`
- Test: `services/api/tests/test_env.py` (new)

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_env.py`:

```python
import os

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for var in ["CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"]:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_celery_defaults_to_localhost_redis(clean_env):
    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://localhost:6379/0"
    assert s.celery_result_backend == "redis://localhost:6379/1"


def test_celery_urls_picked_up_from_env(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "redis://broker.example:6379/5")
    clean_env.setenv("CELERY_RESULT_BACKEND", "redis://broker.example:6379/6")

    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://broker.example:6379/5"
    assert s.celery_result_backend == "redis://broker.example:6379/6"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/api && uv run pytest tests/test_env.py -v
```
Expected: both tests FAIL with `AttributeError: 'Settings' object has no attribute 'celery_broker_url'`.

- [ ] **Step 3: Extend env.py**

Replace the body of `services/api/realty_api/env.py` with:

```python
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    realty_api_key: str = Field(...)
    django_secret_key: str | None = None
    allowed_hosts: str = ""
    csrf_trusted_origins: str = ""
    log_level: str = "INFO"
    timezone: str = "Europe/Amsterdam"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd services/api && uv run pytest tests/test_env.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/realty_api/env.py services/api/tests/test_env.py
git commit -m "feat(api): add celery broker and result backend env settings"
```

---

### Task 3: Wire Celery into Django settings

**Files:**
- Modify: `services/api/realty_api/settings/base.py`
- Modify: `services/api/realty_api/settings/prod.py`

- [ ] **Step 1: Add celery config to `settings/base.py`**

In `services/api/realty_api/settings/base.py`:

1. Add `"django_celery_beat"` to `INSTALLED_APPS` (right after `"scraping"` is fine):

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "scraping",
    "django_celery_beat",
]
```

2. Append the Celery config block after `DEFAULT_AUTO_FIELD = ...`:

```python
# --- Celery ---
CELERY_BROKER_URL = SETTINGS.celery_broker_url
CELERY_RESULT_BACKEND = SETTINGS.celery_result_backend
CELERY_TIMEZONE = SETTINGS.timezone
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
```

- [ ] **Step 2: Require Celery env vars in production**

In `services/api/realty_api/settings/prod.py`, add the validation after the `CSRF_TRUSTED_ORIGINS` block (so it lives with the other required-env-var checks):

```python
if not SETTINGS.celery_broker_url or SETTINGS.celery_broker_url.startswith("redis://localhost"):
    raise ImproperlyConfigured(
        "CELERY_BROKER_URL must be set to a non-localhost redis URL in production.",
    )
if not SETTINGS.celery_result_backend or SETTINGS.celery_result_backend.startswith("redis://localhost"):
    raise ImproperlyConfigured(
        "CELERY_RESULT_BACKEND must be set to a non-localhost redis URL in production.",
    )
```

(The localhost-prefix check exists because the `Settings` class now defaults to localhost — a missing env var would silently fall back to that default without this guard, exactly like the equivalent `DJANGO_SECRET_KEY is None` check earlier in the file.)

- [ ] **Step 3: Verify settings still load**

```bash
cd services/api && uv run python -c "import django; import os; os.environ['DJANGO_SETTINGS_MODULE']='realty_api.settings.local'; django.setup(); from django.conf import settings; print(settings.CELERY_BROKER_URL, settings.CELERY_BEAT_SCHEDULER)"
```
Expected: prints `redis://localhost:6379/0 django_celery_beat.schedulers:DatabaseScheduler`.

- [ ] **Step 4: Run existing tests**

```bash
cd services/api && uv run pytest tests/ -v --create-db
```
The `--create-db` is required ONCE because adding `django_celery_beat` to `INSTALLED_APPS` invalidates the cached test DB schema.
Expected: all existing tests PASS plus the two `test_env.py` tests.

- [ ] **Step 5: Commit**

```bash
git add services/api/realty_api/settings/base.py services/api/realty_api/settings/prod.py
git commit -m "feat(api): configure celery and django-celery-beat in settings"
```

---

### Task 4: Create the Celery app

**Files:**
- Create: `services/api/realty_api/celery.py`
- Modify: `services/api/realty_api/__init__.py`
- Test: `services/api/tests/test_celery.py` (new)
- Modify: `services/api/tests/conftest.py`

- [ ] **Step 1: Add the eager-mode fixture to conftest.py**

Append to `services/api/tests/conftest.py` (no new imports — `settings` is the `pytest-django` built-in fixture):

```python
@pytest.fixture(autouse=True)
def _eager_celery(settings):
    """Run Celery tasks synchronously in-process during tests — no broker needed."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
```

- [ ] **Step 2: Write the failing celery-app test**

Create `services/api/tests/test_celery.py`:

```python
def test_celery_app_is_named_realty_api():
    from realty_api import celery_app

    assert celery_app.main == "realty_api"


def test_celery_app_uses_django_settings_broker():
    from django.conf import settings

    from realty_api import celery_app

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd services/api && uv run pytest tests/test_celery.py -v
```
Expected: FAIL with `ImportError: cannot import name 'celery_app' from 'realty_api'`.

- [ ] **Step 4: Create `realty_api/celery.py`**

Create `services/api/realty_api/celery.py`:

```python
from celery import Celery

app = Celery("realty_api")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

- [ ] **Step 5: Re-export `celery_app` from `realty_api/__init__.py`**

Replace the contents of `services/api/realty_api/__init__.py` with:

```python
from realty_api.celery import app as celery_app

__all__ = ("celery_app",)
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd services/api && uv run pytest tests/test_celery.py -v
```
Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add services/api/realty_api/celery.py services/api/realty_api/__init__.py services/api/tests/conftest.py services/api/tests/test_celery.py
git commit -m "feat(api): instantiate celery app and load django settings"
```

---

### Task 5: Add the `scraping.ping` smoke task

**Files:**
- Create: `services/api/scraping/tasks.py`
- Test: `services/api/tests/test_tasks.py` (new)

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_tasks.py`:

```python
def test_ping_task_is_registered():
    from realty_api import celery_app

    assert "scraping.ping" in celery_app.tasks


def test_ping_returns_pong_under_eager_mode():
    from scraping.tasks import ping

    result = ping.delay()
    assert result.get(timeout=1) == "pong"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd services/api && uv run pytest tests/test_tasks.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scraping.tasks'`.

- [ ] **Step 3: Create the task**

Create `services/api/scraping/tasks.py`:

```python
from celery import shared_task


@shared_task(name="scraping.ping")
def ping() -> str:
    return "pong"
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd services/api && uv run pytest tests/test_tasks.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/tasks.py services/api/tests/test_tasks.py
git commit -m "feat(api): add scraping.ping smoke task for celery plumbing"
```

---

### Task 6: Update `docker-compose.dev.yml`

**Files:**
- Modify: `docker-compose.dev.yml`

- [ ] **Step 1: Replace the file body**

Overwrite `docker-compose.dev.yml` with:

```yaml
services:
  # --- Backend API ---
  api:
    container_name: realty-api
    build:
      context: services/api
    ports:
      - 8000:8000
    environment:
      DJANGO_SETTINGS_MODULE: realty_api.settings.local
      DATABASE_URL: postgres://realty:realty@database:5432/realty_alerts
      REALTY_API_KEY: dev-realty-api-key
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      LOG_LEVEL: DEBUG
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: curl -f http://localhost:8000/healthz || exit 1
      interval: 20s
      timeout: 5s
      retries: 3
      start_period: 10s

  # --- Celery worker ---
  celery-worker:
    container_name: realty-celery-worker
    build:
      context: services/api
    command: ["celery", "-A", "realty_api", "worker", "-l", "info", "--concurrency=2", "--max-tasks-per-child=200"]
    environment:
      DJANGO_SETTINGS_MODULE: realty_api.settings.local
      DATABASE_URL: postgres://realty:realty@database:5432/realty_alerts
      REALTY_API_KEY: dev-realty-api-key
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      LOG_LEVEL: DEBUG
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy

  # --- Celery beat ---
  celery-beat:
    container_name: realty-celery-beat
    build:
      context: services/api
    command: ["celery", "-A", "realty_api", "beat", "-l", "info", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"]
    environment:
      DJANGO_SETTINGS_MODULE: realty_api.settings.local
      DATABASE_URL: postgres://realty:realty@database:5432/realty_alerts
      REALTY_API_KEY: dev-realty-api-key
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      LOG_LEVEL: DEBUG
    depends_on:
      database:
        condition: service_healthy
      redis:
        condition: service_healthy

  # --- Redis (broker + result backend) ---
  redis:
    container_name: realty-redis
    image: redis:8-alpine
    ports:
      - 6379:6379
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # --- Database ---
  database:
    container_name: realty-database
    image: postgres:17.6-alpine
    environment:
      POSTGRES_USER: realty
      POSTGRES_PASSWORD: realty
      POSTGRES_DB: realty_alerts
    ports:
      - 5432:5432
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U realty -d realty_alerts"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s

  # --- Playwright Server (for Funda scraper) ---
  playwright:
    container_name: realty-playwright
    image: mcr.microsoft.com/playwright:v1.53.0-noble
    command: npx -y playwright@1.53.0 run-server --port 3000 --host 0.0.0.0
    ports:
      - 3000:3000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  pgdata:
  redisdata:
```

- [ ] **Step 2: Smoke-test it locally**

```bash
docker compose -f docker-compose.dev.yml up -d --build database redis api celery-worker celery-beat
docker compose -f docker-compose.dev.yml exec api python manage.py migrate
sleep 2
docker compose -f docker-compose.dev.yml exec api \
    python -c "from scraping.tasks import ping; print(ping.delay().get(timeout=10))"
```
Expected: prints `pong`.

```bash
docker compose -f docker-compose.dev.yml logs celery-worker | grep "scraping.ping"
```
Expected: at least one line `Task scraping.ping[<uuid>] succeeded`.

```bash
docker compose -f docker-compose.dev.yml logs celery-beat | head -30
```
Expected: a `Scheduler: Starting...` line, no tracebacks.

- [ ] **Step 3: Tear down**

```bash
docker compose -f docker-compose.dev.yml down
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.dev.yml
git commit -m "build(docker): add redis, celery-worker and celery-beat to dev compose"
```

---

### Task 7: Document the local workflow

**Files:**
- Modify: `services/api/README.md`

- [ ] **Step 1: Add a "Background tasks" section**

Append to `services/api/README.md`:

```markdown
## Background tasks (Celery + Beat)

`make dev` brings up Redis, a Celery worker, and Celery Beat alongside the api and database.

- **Worker:** runs `@shared_task` functions discovered under any installed app (e.g. `scraping.tasks`).
- **Beat:** uses `django_celery_beat.schedulers:DatabaseScheduler`, so periodic tasks live in Postgres
  and are managed at <http://localhost:8000/admin/django_celery_beat/periodictask/> after running
  `make api-superuser`.

Smoke-test from the api container:

\`\`\`bash
docker compose -f docker-compose.dev.yml exec api \
    python -c "from scraping.tasks import ping; print(ping.delay().get(timeout=5))"
\`\`\`

Watch the worker log:

\`\`\`bash
docker compose -f docker-compose.dev.yml logs -f celery-worker
\`\`\`
```

(Replace the `\`\`\`` escapes above with literal triple-backticks when writing the file.)

- [ ] **Step 2: Commit**

```bash
git add services/api/README.md
git commit -m "docs(api): document local celery worker and beat workflow"
```

---

### Task 8: Run pre-commit and full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run pre-commit on all changed files**

```bash
make pre-commit
```
Expected: all hooks pass. If ruff or ty complains, fix the cited file and re-run.

- [ ] **Step 2: Run the API test suite from scratch**

```bash
cd services/api && uv run pytest tests/ -v --create-db
```
Expected: all tests pass, no warnings about missing tables for `django_celery_beat`.

---

### Task 9: Open the realty-alerts PR

**Files:** none (git ops)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin "$(git branch --show-current)"
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat(api): celery + beat + redis foundation" --body "$(cat <<'EOF'
## Summary
- Add `celery[redis]`, `django-celery-beat`, `redis` to `services/api`.
- Wire a Celery app (`realty_api.celery`) using Django settings, with `CELERY_BEAT_SCHEDULER = django_celery_beat.schedulers:DatabaseScheduler`.
- Require `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` in production settings.
- Add a trivial `scraping.ping` smoke task and tests using `CELERY_TASK_ALWAYS_EAGER`.
- Add `redis`, `celery-worker`, `celery-beat` services to `docker-compose.dev.yml`.

This is the foundation only. The Argo Events bridge that uses it to trigger scraper Jobs is a follow-up PR.

Pairs with: `realty-ai-platform` PR adding Redis + worker/beat manifests.

## Test plan
- [ ] `make pre-commit` clean.
- [ ] `cd services/api && uv run pytest tests/ --create-db` green.
- [ ] `make dev` brings up redis/worker/beat without crashes.
- [ ] `ping.delay().get(timeout=5)` returns `"pong"` from inside the api container.
- [ ] Worker log shows `Task scraping.ping... succeeded`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL is printed. Note it for Phase 3.

---

## Phase 2 — `realty-ai-platform`: Kubernetes manifests

> All paths in Phase 2 are relative to `/home/diego/projects/realty-ai-platform`. Start by `cd`-ing there. Use a fresh feature branch (e.g. `feat/api-celery-redis`).

### Task 10: Scaffold the Redis Kustomize app

**Files (in `realty-ai-platform`):**
- Create: `apps/realty-alerts/redis/base/statefulset.yaml`
- Create: `apps/realty-alerts/redis/base/service.yaml`
- Create: `apps/realty-alerts/redis/base/configmap.yaml`
- Create: `apps/realty-alerts/redis/base/kustomization.yaml`

- [ ] **Step 1: Create the directory**

```bash
cd /home/diego/projects/realty-ai-platform
mkdir -p apps/realty-alerts/redis/base apps/realty-alerts/redis/overlays/staging apps/realty-alerts/redis/overlays/production
```

- [ ] **Step 2: Create `redis/base/configmap.yaml`**

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
  labels:
    app: redis
data:
  redis.conf: |
    bind 0.0.0.0
    protected-mode yes
    port 6379
    tcp-keepalive 300
    timeout 0
    appendonly yes
    appendfsync everysec
    maxmemory-policy noeviction
    dir /data
```

- [ ] **Step 3: Create `redis/base/statefulset.yaml`**

```yaml
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  labels:
    app: redis
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:8.0-alpine
          command:
            - sh
            - -c
            - exec redis-server /etc/redis/redis.conf --requirepass "$REDIS_PASSWORD"
          ports:
            - name: redis
              containerPort: 6379
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secrets
                  key: REDIS_PASSWORD
          volumeMounts:
            - name: data
              mountPath: /data
            - name: config
              mountPath: /etc/redis
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              memory: 128Mi
          livenessProbe:
            exec:
              command: ["sh", "-c", 'redis-cli -a "$REDIS_PASSWORD" ping']
            initialDelaySeconds: 10
            periodSeconds: 20
          readinessProbe:
            exec:
              command: ["sh", "-c", 'redis-cli -a "$REDIS_PASSWORD" ping']
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: redis-config
            items:
              - key: redis.conf
                path: redis.conf
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: proxmox-lvm
        resources:
          requests:
            storage: 1Gi
```

- [ ] **Step 4: Create `redis/base/service.yaml`**

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  labels:
    app: redis
spec:
  selector:
    app: redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
      protocol: TCP
```

- [ ] **Step 5: Create `redis/base/kustomization.yaml`**

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - statefulset.yaml
  - service.yaml
  - configmap.yaml
```

- [ ] **Step 6: Validate kustomize build (will fail because no secret yet)**

```bash
kustomize build apps/realty-alerts/redis/base
```
Expected: prints the StatefulSet/Service/ConfigMap YAML cleanly. The base does NOT include the secret — that lives in overlays.

- [ ] **Step 7: Commit**

```bash
git add apps/realty-alerts/redis/base/
git commit -m "feat(redis): scaffold base manifests for celery broker"
```

---

### Task 11: Redis overlays with SOPS-encrypted password

**Files (in `realty-ai-platform`):**
- Create: `apps/realty-alerts/redis/overlays/staging/kustomization.yaml`
- Create: `apps/realty-alerts/redis/overlays/staging/secret-generator.yaml`
- Create: `apps/realty-alerts/redis/overlays/staging/secret.sops.yaml`
- Create: `apps/realty-alerts/redis/overlays/production/kustomization.yaml`
- Create: `apps/realty-alerts/redis/overlays/production/secret-generator.yaml`
- Create: `apps/realty-alerts/redis/overlays/production/secret.sops.yaml`

- [ ] **Step 1: Generate a strong password for staging**

```bash
openssl rand -base64 32
```
Save this value — call it `<STAGING_PW>`. **Do not commit it in cleartext anywhere.**

- [ ] **Step 2: Create `apps/realty-alerts/redis/overlays/staging/secret.sops.yaml` (plaintext form)**

Write a plaintext file first:

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: redis-secrets
type: Opaque
stringData:
  REDIS_PASSWORD: <STAGING_PW>
```

- [ ] **Step 3: Encrypt with SOPS**

```bash
sops --encrypt --in-place apps/realty-alerts/redis/overlays/staging/secret.sops.yaml
```
Expected: file content is now AES256_GCM-encrypted; `apiVersion`, `kind`, `metadata` etc. each show `ENC[AES256_GCM,...]`. Cross-check the output shape against `apps/realty-alerts/api/overlays/staging/secret.sops.yaml`.

- [ ] **Step 4: Create `apps/realty-alerts/redis/overlays/staging/secret-generator.yaml`**

```yaml
apiVersion: viaduct.ai/v1
kind: ksops
metadata:
  name: redis-secrets-generator
  annotations:
    config.kubernetes.io/function: |
      exec:
        path: ksops
files:
  - secret.sops.yaml
```

- [ ] **Step 5: Create `apps/realty-alerts/redis/overlays/staging/kustomization.yaml`**

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: realty-alerts-staging

resources:
  - ../../base

generators:
  - secret-generator.yaml

commonAnnotations:
  argocd.argoproj.io/sync-wave: "-1"
```

- [ ] **Step 6: Repeat steps 1–5 for production**

Generate a **separate** strong password (call it `<PROD_PW>`). Create `apps/realty-alerts/redis/overlays/production/{secret.sops.yaml, secret-generator.yaml, kustomization.yaml}` with the same shape, but:
- `namespace: realty-alerts-production`
- The `kustomization.yaml` ALSO patches the StatefulSet PVC size up to 5Gi:

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: realty-alerts-production

resources:
  - ../../base

generators:
  - secret-generator.yaml

commonAnnotations:
  argocd.argoproj.io/sync-wave: "-1"

patches:
  - target:
      kind: StatefulSet
      name: redis
    patch: |
      - op: replace
        path: /spec/volumeClaimTemplates/0/spec/resources/requests/storage
        value: 5Gi
```

- [ ] **Step 7: Validate both overlays build**

```bash
kustomize build apps/realty-alerts/redis/overlays/staging
kustomize build apps/realty-alerts/redis/overlays/production
```
Expected: both print full manifests including the (still encrypted) Secret resource. Errors here mean a YAML typo — fix before continuing.

- [ ] **Step 8: Save passwords for Phase 2 Task 13**

You will need `<STAGING_PW>` and `<PROD_PW>` again when adding the same passwords to the api overlays. Keep them in your terminal scrollback or a temporary password manager entry. **Do not write them into a file in the repo.**

- [ ] **Step 9: Commit**

```bash
git add apps/realty-alerts/redis/overlays/
git commit -m "feat(redis): add staging and production overlays with sops password"
```

---

### Task 12: ArgoCD Applications for Redis

**Files (in `realty-ai-platform`):**
- Create: `infrastructure/argocd/apps/realty-alerts/realty-alerts-redis-staging.yaml`
- Create: `infrastructure/argocd/apps/realty-alerts/realty-alerts-redis-production.yaml`

- [ ] **Step 1: Create the staging Application**

`infrastructure/argocd/apps/realty-alerts/realty-alerts-redis-staging.yaml`:

```yaml
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: realty-alerts-redis-staging
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: realty-alerts
  source:
    repoURL: https://github.com/DiegoHeer/realty-ai-platform.git
    targetRevision: main
    path: apps/realty-alerts/redis/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: realty-alerts-staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

- [ ] **Step 2: Create the production Application**

`infrastructure/argocd/apps/realty-alerts/realty-alerts-redis-production.yaml`: identical to step 1 but with `name: realty-alerts-redis-production`, `path: apps/realty-alerts/redis/overlays/production`, `namespace: realty-alerts-production`.

- [ ] **Step 3: Commit**

```bash
git add infrastructure/argocd/apps/realty-alerts/realty-alerts-redis-{staging,production}.yaml
git commit -m "feat(argocd): add applications for realty-alerts redis"
```

---

### Task 13: Add Celery worker + beat Deployments to the api app

**Files (in `realty-ai-platform`):**
- Create: `apps/realty-alerts/api/base/deployment-worker.yaml`
- Create: `apps/realty-alerts/api/base/deployment-beat.yaml`
- Modify: `apps/realty-alerts/api/base/configmap.yaml`
- Modify: `apps/realty-alerts/api/base/deployment.yaml`
- Modify: `apps/realty-alerts/api/base/kustomization.yaml`

- [ ] **Step 1: Update `apps/realty-alerts/api/base/configmap.yaml`**

Add the two Celery URL entries (note the `$(REDIS_PASSWORD)` template — Kubernetes will substitute when each pod's `env:` provides it):

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  labels:
    app: api
data:
  DJANGO_SETTINGS_MODULE: "realty_api.settings.prod"
  ALLOWED_HOSTS: "api.realty-ai.nl,api"
  CSRF_TRUSTED_ORIGINS: "https://api.realty-ai.nl"
  LOG_LEVEL: "INFO"
  TIMEZONE: "Europe/Amsterdam"
  CELERY_BROKER_URL: "redis://:$(REDIS_PASSWORD)@redis:6379/0"
  CELERY_RESULT_BACKEND: "redis://:$(REDIS_PASSWORD)@redis:6379/1"
```

- [ ] **Step 2: Update `apps/realty-alerts/api/base/deployment.yaml` (web pod)**

Add an explicit `env:` block on the web container so Kubernetes can substitute `$(REDIS_PASSWORD)` from the secret into the ConfigMap-supplied URLs. Insert this block after the existing `envFrom:`:

```yaml
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secrets
                  key: REDIS_PASSWORD
```

- [ ] **Step 3: Create `apps/realty-alerts/api/base/deployment-worker.yaml`**

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-worker
  labels:
    app: api-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-worker
  template:
    metadata:
      labels:
        app: api-worker
    spec:
      containers:
        - name: worker
          image: ghcr.io/diegoheer/realty-alerts/api
          command:
            - sh
            - -c
            - python manage.py migrate --noinput && exec celery -A realty_api worker -l info --concurrency=2 --max-tasks-per-child=200
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: api-secrets
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secrets
                  key: REDIS_PASSWORD
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              memory: 256Mi
```

- [ ] **Step 4: Create `apps/realty-alerts/api/base/deployment-beat.yaml`**

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-beat
  labels:
    app: api-beat
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: api-beat
  template:
    metadata:
      labels:
        app: api-beat
    spec:
      containers:
        - name: beat
          image: ghcr.io/diegoheer/realty-alerts/api
          command:
            - sh
            - -c
            - python manage.py migrate --noinput && exec celery -A realty_api beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: api-secrets
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secrets
                  key: REDIS_PASSWORD
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              memory: 128Mi
```

- [ ] **Step 5: Update `apps/realty-alerts/api/base/kustomization.yaml`**

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - deployment-worker.yaml
  - deployment-beat.yaml
  - service.yaml
  - ingress.yaml
  - configmap.yaml
```

- [ ] **Step 6: Validate the api base builds**

```bash
kustomize build apps/realty-alerts/api/base
```
Expected: prints all five resources (web Deployment, worker Deployment, beat Deployment, Service, Ingress, ConfigMap).

- [ ] **Step 7: Commit**

```bash
git add apps/realty-alerts/api/base/
git commit -m "feat(api): add celery worker and beat deployments"
```

---

### Task 14: Per-overlay redis-secrets for staging and production

**Files (in `realty-ai-platform`):**
- Create: `apps/realty-alerts/api/overlays/staging/redis-secret-generator.yaml`
- Create: `apps/realty-alerts/api/overlays/staging/redis-secret.sops.yaml`
- Modify: `apps/realty-alerts/api/overlays/staging/kustomization.yaml`
- Create: `apps/realty-alerts/api/overlays/production/redis-secret-generator.yaml`
- Create: `apps/realty-alerts/api/overlays/production/redis-secret.sops.yaml`
- Modify: `apps/realty-alerts/api/overlays/production/kustomization.yaml`

- [ ] **Step 1: Plaintext staging secret file**

`apps/realty-alerts/api/overlays/staging/redis-secret.sops.yaml`:

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: redis-secrets
type: Opaque
stringData:
  REDIS_PASSWORD: <STAGING_PW>
```

Use the **same** `<STAGING_PW>` from Task 11 step 1.

- [ ] **Step 2: Encrypt it**

```bash
sops --encrypt --in-place apps/realty-alerts/api/overlays/staging/redis-secret.sops.yaml
```

- [ ] **Step 3: Staging KSOPS generator**

`apps/realty-alerts/api/overlays/staging/redis-secret-generator.yaml`:

```yaml
apiVersion: viaduct.ai/v1
kind: ksops
metadata:
  name: redis-secrets-generator
  annotations:
    config.kubernetes.io/function: |
      exec:
        path: ksops
files:
  - redis-secret.sops.yaml
```

- [ ] **Step 4: Add it to the staging kustomization**

In `apps/realty-alerts/api/overlays/staging/kustomization.yaml`, append the new generator to the existing `generators:` list:

```yaml
generators:
- secret-generator.yaml
- redis-secret-generator.yaml
```

- [ ] **Step 5: Repeat steps 1–4 for production**

Same shape, in `apps/realty-alerts/api/overlays/production/`, using `<PROD_PW>` from Task 11 step 6.

- [ ] **Step 6: Validate both overlays**

```bash
kustomize build apps/realty-alerts/api/overlays/staging
kustomize build apps/realty-alerts/api/overlays/production
```
Expected: each prints the api manifests including TWO Secret resources (`api-secrets` and `redis-secrets`). The web/worker/beat Deployments should each show the `REDIS_PASSWORD` env entry referencing `redis-secrets`.

- [ ] **Step 7: Commit**

```bash
git add apps/realty-alerts/api/overlays/staging/redis-secret-generator.yaml \
        apps/realty-alerts/api/overlays/staging/redis-secret.sops.yaml \
        apps/realty-alerts/api/overlays/staging/kustomization.yaml \
        apps/realty-alerts/api/overlays/production/redis-secret-generator.yaml \
        apps/realty-alerts/api/overlays/production/redis-secret.sops.yaml \
        apps/realty-alerts/api/overlays/production/kustomization.yaml
git commit -m "feat(api): wire redis-secrets into staging and production overlays"
```

---

### Task 15: Exclude worker/beat from the preview overlay

**Files (in `realty-ai-platform`):**
- Create: `apps/realty-alerts/api/overlays/preview/delete-worker.yaml`
- Create: `apps/realty-alerts/api/overlays/preview/delete-beat.yaml`
- Modify: `apps/realty-alerts/api/overlays/preview/kustomization.yaml`

- [ ] **Step 1: Create the delete patches**

`apps/realty-alerts/api/overlays/preview/delete-worker.yaml`:

```yaml
---
$patch: delete
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-worker
```

`apps/realty-alerts/api/overlays/preview/delete-beat.yaml`:

```yaml
---
$patch: delete
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-beat
```

- [ ] **Step 2: Update preview kustomization**

In `apps/realty-alerts/api/overlays/preview/kustomization.yaml`, add a `patches:` block alongside the existing entries:

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

generators:
  - secret-generator.yaml

patches:
  - path: delete-worker.yaml
  - path: delete-beat.yaml

images:
  - name: ghcr.io/diegoheer/realty-alerts/api
    newTag: pr-N
```

(Preserve any existing `patches:` already present in the file — append, don't replace.)

- [ ] **Step 3: Validate the preview build**

```bash
kustomize build apps/realty-alerts/api/overlays/preview
```
Expected: Output contains the web `Deployment` named `api` and Service/Ingress/ConfigMap, but **NOT** `api-worker` or `api-beat`.

Verify with grep:

```bash
kustomize build apps/realty-alerts/api/overlays/preview | grep -E "^  name: api(-worker|-beat)?$"
```
Expected: only `name: api` appears (twice — Deployment + Service).

- [ ] **Step 4: Commit**

```bash
git add apps/realty-alerts/api/overlays/preview/
git commit -m "feat(api): exclude celery worker and beat from preview overlay"
```

---

### Task 16: Open the platform PR

**Files (in `realty-ai-platform`):** none (git ops)

- [ ] **Step 1: Push the branch**

```bash
cd /home/diego/projects/realty-ai-platform
git push -u origin "$(git branch --show-current)"
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat(realty-alerts): celery worker + beat + redis manifests" --body "$(cat <<'EOF'
## Summary
- New Kustomize app `apps/realty-alerts/redis/` (StatefulSet + Service + ConfigMap, AOF on, requirepass), with staging and production overlays.
- Two new ArgoCD Applications (`realty-alerts-redis-{staging,production}`) under the existing `realty-alerts` AppProject. Sync-wave `-1` so Redis comes up before the api app.
- `apps/realty-alerts/api/base/` now contains `deployment-worker.yaml` and `deployment-beat.yaml` alongside the existing web Deployment. All three share the api image; only `command:` differs. Worker/beat run `migrate --noinput` before starting so the django-celery-beat tables exist regardless of which pod boots first.
- `api-config` ConfigMap gets `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` entries that reference `$(REDIS_PASSWORD)`. Web/worker/beat all gain a `REDIS_PASSWORD` env entry pulled from the new `redis-secrets` Secret so substitution works.
- New SOPS-encrypted `redis-secrets` Secret in `apps/realty-alerts/api/overlays/{staging,production}/`, mirroring the same password held in `apps/realty-alerts/redis/overlays/<env>/`.
- Preview overlay deletes the worker and beat Deployments via `$patch: delete` (per-PR namespaces have no Redis).

Pairs with the realty-alerts repo PR adding the Python-side wiring. **Merge the realty-alerts PR first**, wait for the new api image tag to be pinned in the staging overlay, then merge this one.

## Test plan
- [ ] `kustomize build apps/realty-alerts/redis/overlays/staging` succeeds.
- [ ] `kustomize build apps/realty-alerts/redis/overlays/production` succeeds.
- [ ] `kustomize build apps/realty-alerts/api/overlays/staging` succeeds and contains both `api-secrets` and `redis-secrets`.
- [ ] `kustomize build apps/realty-alerts/api/overlays/production` succeeds.
- [ ] `kustomize build apps/realty-alerts/api/overlays/preview` succeeds and does NOT contain `api-worker` or `api-beat`.
- [ ] After merge: `kubectl -n realty-alerts-staging exec deploy/api-worker -- celery -A realty_api inspect ping` returns `pong: OK`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase 3 — Cross-repo merge ordering

### Task 17: Coordinated rollout

**Files:** none (release process)

- [ ] **Step 1: Merge the `realty-alerts` PR first**

`gh pr merge --merge <pr-number>` (per the project's `feedback_merge_strategy.md` memory — never squash). This triggers the existing CI gitops job to bump the api image tag in `apps/realty-alerts/api/overlays/staging/kustomization.yaml` of `realty-ai-platform`.

- [ ] **Step 2: Rebase the platform PR on the bumped main**

```bash
cd /home/diego/projects/realty-ai-platform
git fetch origin
git rebase origin/main
git push --force-with-lease
```

- [ ] **Step 3: Merge the `realty-ai-platform` PR**

`gh pr merge --merge <pr-number>`.

- [ ] **Step 4: Watch ArgoCD reconcile**

ArgoCD picks up the changes:
1. `realty-alerts-redis-staging` (sync-wave -1) syncs first → Redis StatefulSet bootstraps, PVC binds.
2. `realty-alerts-api-staging` (default sync-wave 0) syncs → web/worker/beat Deployments roll. Each pod runs `migrate --noinput` on startup; the first one wins the migration lock, the rest see "no migrations to apply".

```bash
kubectl -n realty-alerts-staging get pods -w
```
Expected: `redis-0` Ready first, then `api`, `api-worker`, `api-beat` Pods Ready.

- [ ] **Step 5: Smoke test in staging**

```bash
kubectl -n realty-alerts-staging exec deploy/api-worker -- celery -A realty_api inspect ping
```
Expected: `-> celery@<pod-name>: OK\n    pong`.

```bash
kubectl -n realty-alerts-staging logs deploy/api-beat | head -30
```
Expected: a `Scheduler: Starting...` line, no tracebacks. (No PeriodicTasks defined yet — Beat is just polling Postgres for the empty `django_celery_beat_periodictask` table.)

- [ ] **Step 6: Promote to production**

When staging is verified, merge the next CI gitops bump PR (it will update the production overlay tag the same way staging was updated). Repeat the smoke test commands against `-n realty-alerts-production`.

---

## Verification (end-to-end)

The full feature is verified when, in production:

1. `kubectl -n realty-alerts-production exec deploy/api -- python manage.py shell -c "from scraping.tasks import ping; print(ping.delay().id)"` returns a UUID.
2. `kubectl -n realty-alerts-production logs deploy/api-worker | grep "Task scraping.ping"` shows a `succeeded` line.
3. `https://api.realty-ai.nl/admin/django_celery_beat/periodictask/` is reachable for an authenticated superuser. Adding a `Clocked` one-off `PeriodicTask` for `scraping.ping` ~30s in the future causes the worker log to record an execution.

That's the foundation. The follow-up PR replaces `apps/realty-alerts/scraper/base/cronjob.yaml` with a real Celery task + Argo Events webhook bridge; this is explicitly out of scope here.
