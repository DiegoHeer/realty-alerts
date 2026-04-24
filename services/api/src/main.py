import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.routers import filters, health, internal, listings, scrape_runs, users
from config import Settings

settings = Settings()


def create_app() -> FastAPI:
    app = FastAPI(title="Realty Alerts API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(filters.router, prefix="/api/v1")
    app.include_router(listings.router, prefix="/api/v1")
    app.include_router(scrape_runs.router, prefix="/api/v1")
    app.include_router(internal.router, prefix="/internal/v1")

    return app


def run_api() -> None:
    """
    Entrypoint for the API
    """
    try:
        logger.info("Starting uvicorn server...")

        app = create_app()
        uvicorn.run(app=app, host=settings.host, port=settings.port, log_level=settings.log_level)

        logger.info("Stopped uvicorn server.")
    except Exception as exc:
        logger.exception(f"Uvicorn server failure: {exc}")
        exit(1)


if __name__ == "__main__":
    run_api()
