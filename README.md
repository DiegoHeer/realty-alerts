# Realty Alerts

Real estate listing notifications for the Dutch housing market. Get push notifications when new properties appear on Funda, Pararius, and Vastgoed Nederland.

## Architecture

Application monorepo with 4 services. Deployment is GitOps — see [realty-ai-platform](https://github.com/DiegoHeer/realty-ai-platform) for the cluster and ArgoCD configuration.

```
services/
  scraper/     CDC scraper (Python, K8s CronJobs per website)
  api/         Django 6.0 + Django Ninja backend (Django ORM, psycopg3)
apps/
  mobile/      React Native / Expo (TanStack Query, Zustand)
  web/         Next.js static landing page (Tailwind CSS)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Django 6.0, Django Ninja, Django ORM, psycopg3, Gunicorn, WhiteNoise |
| Scraper | Python, BeautifulSoup, Playwright, httpx |
| Mobile App | React Native, Expo, TanStack Query, Zustand |
| Landing Page | Next.js 15, Tailwind CSS |
| Database | PostgreSQL |
| Notifications | Expo Push (FCM/APNs) |
| Deployment | GitOps — [realty-ai-platform](https://github.com/DiegoHeer/realty-ai-platform) |
| CI/CD | GitHub Actions (per-service path-filtered workflows building & pushing images to GHCR) |

## Supported Websites

- [Funda](https://www.funda.nl) (Playwright)
- [Pararius](https://www.pararius.nl) (Playwright)
- [Vastgoed Nederland](https://aanbod.vastgoednederland.nl) (HTTP)

## Local Development

```bash
# Start database + Playwright (for scraper testing)
docker compose -f docker-compose.dev.yml up -d

# Backend API
cd services/api && uv sync --dev
make api

# Scraper tests
cd services/scraper && uv sync --dev
uv run pytest tests/ -v

# Mobile app (requires Node.js)
cd apps/mobile && npm install
npx expo start

# Landing page (requires Node.js)
cd apps/web && npm install
npm run dev
```

Or use the root Makefile:

```bash
make help          # show all targets
make dev           # start all via docker-compose
make lint          # lint all Python services
make test          # run all tests
make build         # build all Docker images
```

## Deployment

This repo builds container images and pushes them to GHCR. Cluster provisioning, Kubernetes manifests, and ArgoCD reconciliation live in [realty-ai-platform](https://github.com/DiegoHeer/realty-ai-platform).
