"""Churn prediction API endpoints per 05_API_SPEC.md §8."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MLError, NotFoundError
from app.infrastructure.database.session import engine, get_session
from app.ml.predict import predict_customer
from app.schemas.churn import ChurnPredictRequest
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/api/v1/churn", tags=["churn"])


@router.post("/predict", response_model=SuccessResponse[dict[str, object]])
async def predict_single(
    request: Request,
    body: ChurnPredictRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SuccessResponse[dict[str, object]]:
    """Online churn prediction for a single customer (05_API_SPEC §8.2)."""
    customer_id = body.customer_id

    try:
        prediction = await predict_customer(engine, str(customer_id))
    except RuntimeError as exc:
        raise MLError(code="ML_002", message=str(exc)) from exc

    if prediction is None:
        raise NotFoundError(code="NF_001", message=f"Customer not found: {customer_id}")

    return SuccessResponse(
        data=prediction,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post("/predict/batch", response_model=SuccessResponse[dict[str, object]])
async def predict_batch_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SuccessResponse[dict[str, object]]:
    """Trigger batch prediction for all customers (05_API_SPEC §8.3)."""
    from app.ml.predict import predict_batch

    try:
        count = await predict_batch(engine)
    except RuntimeError as exc:
        raise MLError(code="ML_002", message=str(exc)) from exc

    return SuccessResponse(
        data={"task_id": f"task_batch_{count}", "status": "COMPLETED", "count": count},
        request_id=getattr(request.state, "request_id", ""),
    )
