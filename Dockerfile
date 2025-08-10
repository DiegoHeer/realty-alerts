FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Change the working directory to the `app` directory
WORKDIR /app

# Sync the project into a new environment, asserting the lockfile is up to date
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev --compile-bytecode

# Copy the project into the image
ADD ./src ./

# Set standard env variables
ENV PATH="/app/.venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE="core.settings.prod"

# Copy and enable the Django entrypoint script
COPY ./django_setup.sh ./django_setup.sh
RUN chmod +x ./django_setup.sh
