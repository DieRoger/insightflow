"""System endpoints: health, metrics, async task polling.

The /system/health endpoint is the Walking Skeleton — it exercises the
full chain: FastAPI router → async database connection → standard envelope.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.session import check_database_connection
from app.schemas.common import SuccessResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class HealthChecks(BaseModel):
    """Per-dependency health status."""

    database: str = "unknown"


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str
    version: str
    checks: HealthChecks


@router.get("/health", response_model=SuccessResponse[HealthResponse])
async def health(
    request: Request,
    db_ok: bool = Depends(check_database_connection),
) -> SuccessResponse[HealthResponse]:
    """Liveness/readiness check. Verifies real database connectivity."""
    checks = HealthChecks(database="ok" if db_ok else "degraded")
    status = "healthy" if db_ok else "degraded"
    logger.info("health_check", status=status, database=checks.database)
    return SuccessResponse(
        data=HealthResponse(
            status=status,
            version=settings.app_version,
            checks=checks,
        ),
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/metrics", response_model=SuccessResponse[dict[str, int | float]])
async def metrics(request: Request) -> SuccessResponse[dict[str, int | float]]:
    """Internal observability metrics (placeholder for MVP)."""
    return SuccessResponse(
        data={
            "requests_total": 0,
            "avg_latency_ms": 0,
            "error_rate": 0.0,
        },
        request_id=getattr(request.state, "request_id", ""),
    )
