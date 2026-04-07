from fastapi import FastAPI

from app.routers import filters, health, internal, listings, scrape_runs, users


def create_app() -> FastAPI:
    app = FastAPI(title="Realty Alerts API", version="0.1.0")

    app.include_router(health.router)
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(filters.router, prefix="/api/v1")
    app.include_router(listings.router, prefix="/api/v1")
    app.include_router(scrape_runs.router, prefix="/api/v1")
    app.include_router(internal.router, prefix="/internal/v1")

    return app
