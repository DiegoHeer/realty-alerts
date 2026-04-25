FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --compile-bytecode

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:create_app --factory --host 0.0.0.0 --port 8000"]
