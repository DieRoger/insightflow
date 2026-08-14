"""Analytics API endpoints per 05_API_SPEC.md §6."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.analytics.analytics_service import AnalyticsService
from app.core.exceptions import NotFoundError
from app.infrastructure.database.session import get_session
from app.infrastructure.repositories.kpi_repository import KpiRepositorySQL
from app.infrastructure.repositories.metric_repository import MetricRepository
from app.schemas.common import Meta, SuccessResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> AnalyticsService:
    return AnalyticsService(session, MetricRepository(session), KpiRepositorySQL(session))


@router.get("/kpi", response_model=SuccessResponse[dict[str, object]])
async def list_kpis(
    request: Request,
    service: Annotated[AnalyticsService, Depends(_service)],
    metric: str | None = Query(default=None),
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    period: str = Query(default="2026-07"),
) -> SuccessResponse[dict[str, object]]:
    """List KPI values with optional filters (05_API_SPEC §6.1)."""
    items = await service.list_kpis(metric=metric, category=category, region=region, period=period)
    return SuccessResponse(
        data={"items": items},
        meta=Meta(page=1, page_size=len(items), total=len(items)),
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/kpi/{metric_name}", response_model=SuccessResponse[dict[str, object]])
async def get_kpi_trend(
    request: Request,
    metric_name: str,
    service: Annotated[AnalyticsService, Depends(_service)],
    granularity: str = Query(default="month"),
    periods: int = Query(default=12, ge=1, le=60),
) -> SuccessResponse[dict[str, object]]:
    """Trend data for a single metric (05_API_SPEC §6.2)."""
    data = await service.get_metric_trend(metric_name, granularity, periods)
    if data is None:
        raise NotFoundError(code="NF_001", message=f"Metric not found: {metric_name}")
    return SuccessResponse(
        data=data,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/anomaly", response_model=SuccessResponse[dict[str, object]])
async def list_anomalies(
    request: Request,
    service: Annotated[AnalyticsService, Depends(_service)],
    metric: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> SuccessResponse[dict[str, object]]:
    """List active anomalies (05_API_SPEC §6.4)."""
    items = await service.list_anomalies(metric=metric, limit=limit)
    return SuccessResponse(
        data={"items": items},
        meta=Meta(total=len(items)),
        request_id=getattr(request.state, "request_id", ""),
    )
