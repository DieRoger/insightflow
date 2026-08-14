"""Customer API endpoints per 05_API_SPEC.md §7."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.customer.entities import Customer, CustomerFilters
from app.infrastructure.database.session import get_session
from app.infrastructure.repositories.customer_repository import CustomerRepositorySQL
from app.schemas.common import Meta, SuccessResponse

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=SuccessResponse[dict[str, object]])
async def list_customers(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    lifecycle_stage: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    region: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="tenure_days"),
    order: str = Query(default="desc"),
) -> SuccessResponse[dict[str, object]]:
    """List/search customers with pagination (05_API_SPEC §7.1)."""
    repo = CustomerRepositorySQL(session)
    filters = CustomerFilters(
        status=status,
        segment=segment,
        lifecycle_stage=lifecycle_stage,
        risk_level=risk_level,
        region=region,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    result = await repo.search(filters)

    items = []
    for customer in result.items:
        risk_score = getattr(customer, "risk_score", None)
        items.append(
            {
                "customer_id": customer.source_customer_id,
                "status": customer.status,
                "lifecycle_stage": customer.lifecycle_stage,
                "segment": customer.segment,
                "churn_risk_score": risk_score,
                "risk_level": _risk_level(risk_score),
                "arpu": None,
                "tenure_days": customer.tenure_days,
                "region": customer.region,
                "package_name": customer.package_name,
                "join_date": customer.join_date.isoformat(),
            }
        )

    return SuccessResponse(
        data={"items": items},
        meta=Meta(
            page=result.page,
            page_size=result.page_size,
            total=result.total,
            total_pages=result.total_pages,
        ),
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get("/{customer_id}", response_model=SuccessResponse[dict[str, object]])
async def get_customer(
    request: Request,
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SuccessResponse[dict[str, object]]:
    """Customer 360 profile (05_API_SPEC §7.2)."""
    repo = CustomerRepositorySQL(session)
    customer = await repo.get_by_source_id(customer_id)
    if customer is None:
        raise NotFoundError(code="NF_001", message=f"Customer with ID {customer_id} does not exist")

    profile = await _build_profile(session, customer)
    return SuccessResponse(
        data=profile,
        request_id=getattr(request.state, "request_id", ""),
    )


def _risk_level(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.7:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


async def _build_profile(session: AsyncSession, customer: Customer) -> dict[str, object]:
    """Assemble the 10-section Customer 360 payload.

    All data access goes through the repository (AR-050/AR-055) — the
    router never executes SQL directly (AR-003).
    """
    repo = CustomerRepositorySQL(session)

    usage = await repo.get_usage_summary(customer.customer_id)
    billing = await repo.get_billing_summary(customer.customer_id)
    service = await repo.get_service_summary(customer.customer_id)
    prediction = await repo.get_latest_prediction(customer.customer_id)

    avg_data, avg_voice, peak_ratio = usage
    arpu, last_payment, overdue = billing
    complaints, avg_csat, avg_resolution = service
    risk_score, risk_level = prediction

    return {
        "profile": {
            "customer_id": customer.source_customer_id,
            "gender": customer.gender,
            "age": customer.age,
            "city": customer.city,
            "region": customer.region,
            "join_date": customer.join_date.isoformat(),
            "contract_type": customer.contract_type,
            "status": customer.status,
            "lifecycle_stage": customer.lifecycle_stage,
            "segment": customer.segment,
            "tenure_days": customer.tenure_days,
        },
        "package": {
            "package_name": customer.package_name,
            "monthly_price": None,
        },
        "billing": {
            "arpu": arpu,
            "last_payment_status": last_payment,
            "overdue_days": overdue,
            "discount_ratio": None,
            "monthly_bills": [],
        },
        "usage": {
            "avg_daily_data_mb": round(avg_data, 2) if avg_data is not None else None,
            "avg_daily_voice_min": round(avg_voice, 2) if avg_voice is not None else None,
            "peak_usage_ratio": round(peak_ratio, 4) if peak_ratio is not None else None,
        },
        "network": {
            "avg_latency_ms": None,
            "drop_rate": None,
            "coverage_score": None,
        },
        "service": {
            "total_complaints_90d": complaints,
            "avg_csat": round(avg_csat, 2) if avg_csat is not None else None,
            "avg_resolution_time_min": (
                round(avg_resolution, 2) if avg_resolution is not None else None
            ),
        },
        "prediction": {
            "churn_risk_score": risk_score,
            "risk_level": risk_level,
            "top_risk_factors": [],
            "predicted_at": None,
        },
        "recommendations": [],
        "timeline": [],
    }
