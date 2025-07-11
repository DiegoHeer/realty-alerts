FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Change the working directory to the `app` directory
WORKDIR /app

# Sync the project into a new environment, asserting the lockfile is up to date
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --compile-bytecode

# Copy the project into the image
ADD ./src ./

# Use the new environment
ENV PATH="/app/.venv/bin:$PATH"

# Run the application
CMD ["celery", "-A", "tasks", "worker", "-B", "--loglevel=info", "--pidfile=/tmp/celery-beat.pid"]
