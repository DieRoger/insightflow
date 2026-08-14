"""Domain-facing CustomerRepository interface."""

from abc import ABC, abstractmethod

from app.domain.customer.entities import Customer, CustomerFilters, PaginatedResult


class CustomerRepository(ABC):
    """Persistence contract for customer data (AR-050)."""

    @abstractmethod
    async def get_by_id(self, customer_id: int) -> Customer | None:
        """Retrieve a single customer by warehouse surrogate key."""

    @abstractmethod
    async def get_by_source_id(self, source_customer_id: str) -> Customer | None:
        """Retrieve a single customer by source system customer ID."""

    @abstractmethod
    async def search(self, filters: CustomerFilters) -> PaginatedResult[Customer]:
        """Search customers with pagination and filters."""
