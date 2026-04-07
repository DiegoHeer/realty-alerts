# Realty Alerts

Real estate listing notifications for the Dutch housing market. Get push notifications when new properties appear on Funda, Pararius, and Vastgoed Nederland.

## Architecture

Monorepo with 5 services, deployed on self-hosted Proxmox + k3s:

```
services/
  scraper/     CDC scraper (Python, K8s CronJobs per website)
  api/         FastAPI backend (SQLModel, Alembic, Supabase Auth)
apps/
  mobile/      React Native / Expo (TanStack Query, Zustand)
  web/         Next.js static landing page (Tailwind CSS)
infra/
  terraform/   Proxmox VMs, k3s, K8s resources, Supabase, monitoring
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, SQLModel, Alembic, asyncpg |
| Scraper | Python, BeautifulSoup, Playwright, httpx |
| Mobile App | React Native, Expo, TanStack Query, Zustand |
| Landing Page | Next.js 15, Tailwind CSS |
| Auth | Supabase Auth (self-hosted) |
| Database | PostgreSQL (via Supabase) |
| Real-time | Supabase Realtime |
| Notifications | Expo Push (FCM/APNs) |
| Infrastructure | Proxmox, k3s, Terraform |
| Monitoring | VictoriaMetrics, Grafana Alloy, Grafana |
| CI/CD | GitHub Actions (per-service path-filtered workflows) |

## Supported Websites

- [Funda](https://www.funda.nl) (Playwright)
- [Pararius](https://www.pararius.nl) (HTTP)
- [Vastgoed Nederland](https://aanbod.vastgoednederland.nl) (HTTP)

## Local Development

```bash
# Start database + Playwright (for scraper testing)
docker compose -f docker-compose.dev.yml up -d

# Backend API
cd services/api && uv sync --dev
make api-dev

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

## Infrastructure

Terraform manages the full stack from Proxmox VMs to application deployments:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=dev.tfvars     # dev environment
terraform plan -var-file=prod.tfvars    # prod environment
```

See the [plan document](.claude/plans/vivid-coalescing-toast.md) for the full architecture design.
