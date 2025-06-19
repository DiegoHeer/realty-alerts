FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Change the working directory to the `app` directory
WORKDIR /app

# Sync the project into a new environment, asserting the lockfile is up to date
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked

# Copy the project into the image
ADD ./src ./

# Run the application
CMD ["uv", "run", "main.py"]
