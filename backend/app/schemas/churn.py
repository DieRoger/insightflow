"""Pydantic schemas for churn endpoints (05_API_SPEC §8)."""

from pydantic import BaseModel, Field


class ChurnPredictRequest(BaseModel):
    """Request body for POST /api/v1/churn/predict."""

    customer_id: str = Field(..., min_length=1, max_length=50, description="Source customer ID")
