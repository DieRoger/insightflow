"""InsightFlow FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.routers import analytics, customers, system
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI app."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware (inner) then error handlers
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)

    # Routers
    app.include_router(system.router)
    app.include_router(analytics.router)
    app.include_router(customers.router)

    return app


app = create_app()
