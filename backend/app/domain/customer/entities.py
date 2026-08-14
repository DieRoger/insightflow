"""Customer domain entities."""

from dataclasses import dataclass
from datetime import date
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CustomerFilters:
    """Search filters for the customer list endpoint."""

    status: str | None = None
    segment: str | None = None
    lifecycle_stage: str | None = None
    risk_level: str | None = None
    region: str | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 20
    sort: str = "tenure_days"
    order: str = "desc"


@dataclass(frozen=True)
class PaginatedResult(Generic[T]):
    """Paginated collection of domain entities."""

    items: list[T]
    page: int
    page_size: int
    total: int

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size else 0


@dataclass
class Customer:
    """Customer aggregate root (zero framework imports)."""

    customer_id: int
    source_customer_id: str
    status: str
    lifecycle_stage: str
    join_date: date
    contract_type: str
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    province: str | None = None
    region: str | None = None
    package_name: str | None = None
    segment: str | None = None
    clv: float | None = None
    tenure_days: int = 0
    risk_score: float | None = None

    def __post_init__(self) -> None:
        self.tenure_days = (date.today() - self.join_date).days if self.join_date else 0
