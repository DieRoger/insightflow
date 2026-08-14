"""Standard API response envelope shared by every endpoint.

Success:  { "success": true,  "data": ..., "meta": ..., "request_id": ... }
Error:    { "success": false, "error": {...}, "request_id": ... }
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    """Pagination and latency metadata."""

    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    total_pages: int | None = None
    latency_ms: int | None = None


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success envelope."""

    success: bool = True
    data: T
    meta: Meta | None = None
    request_id: str


class ErrorDetail(BaseModel):
    """Standard error payload."""

    code: str
    message: str
    details: dict[str, object] | None = None
    category: str = "INTERNAL"


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    success: bool = False
    error: ErrorDetail
    request_id: str
