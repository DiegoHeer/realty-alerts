# web

Next.js 15 static landing page (Tailwind CSS v4, Framer Motion). Built as a static export and served by nginx in production.

## Development

```bash
npm ci
npm run dev    # next dev on :3000
npm run lint
npm test       # vitest
npm run build  # static export to ./out
```

The Docker image is `ghcr.io/diegoheer/realty-alerts/web` — built and pushed by [.github/workflows/web.yml](../../.github/workflows/web.yml). On merge to `main`, that workflow opens a `release/web-sha-…` PR on `realty-ai-platform` to promote the new image to production. See the repo-level [CLAUDE.md](../../CLAUDE.md) for project-wide conventions.
