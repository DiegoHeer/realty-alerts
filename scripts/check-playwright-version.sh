#!/usr/bin/env bash
# Asserts that docker-compose.dev.yml's Playwright server pin matches the
# scraper's locked playwright client. The two negotiate a WS protocol whose
# shape changes between minor versions, so any skew silently breaks `make dev`
# scrapes with `BrowserType.connect: WebSocket error: 400 Bad Request`.
set -euo pipefail

locked=$(awk '/^name = "playwright"$/{getline; gsub(/[^0-9.]/,""); print; exit}' \
  services/scraper/uv.lock)
image=$(grep -oE 'mcr\.microsoft\.com/playwright:v[0-9.]+' \
  docker-compose.dev.yml | head -1 | sed 's/.*v//')
cmd=$(grep -oE 'playwright@[0-9.]+' docker-compose.dev.yml | head -1 | sed 's/.*@//')

if [[ -z "$locked" || -z "$image" || -z "$cmd" ]]; then
  echo "playwright-version-sync: failed to parse one of uv.lock or docker-compose.dev.yml" >&2
  echo "  uv.lock pin:    '${locked}'" >&2
  echo "  compose image:  '${image}'" >&2
  echo "  compose cmd:    '${cmd}'" >&2
  exit 1
fi

if [[ "$locked" != "$image" || "$locked" != "$cmd" ]]; then
  cat >&2 <<EOF
Playwright client/server version skew detected:
  services/scraper/uv.lock pin:        $locked
  docker-compose.dev.yml image tag:    $image
  docker-compose.dev.yml run-server:   $cmd

Update docker-compose.dev.yml so both the image tag and the
\`playwright@X.Y.Z\` command match $locked.
EOF
  exit 1
fi
