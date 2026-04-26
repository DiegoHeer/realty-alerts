FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --compile-bytecode

COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"

# This image deliberately does NOT bundle Playwright browsers.
# The scraper connects to a remote Playwright server at $BROWSER_URL (ws://...).
CMD ["python", "-m", "scraper"]
