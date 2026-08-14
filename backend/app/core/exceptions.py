"""Typed exception hierarchy for InsightFlow.

Every business failure is raised as a typed InsightFlowError carrying a
stable error code, matching the error code registry in 05_API_SPEC.md §5.
"""


class InsightFlowError(Exception):
    """Base exception for all InsightFlow errors."""

    category = "INTERNAL"

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class ValidationError(InsightFlowError):
    """Invalid request data (HTTP 422)."""

    category = "VALIDATION"


class BusinessError(InsightFlowError):
    """Business rule violation (HTTP 409)."""

    category = "BUSINESS"


class NotFoundError(InsightFlowError):
    """Resource not found (HTTP 404)."""

    category = "NOT_FOUND"


class MLError(InsightFlowError):
    """ML pipeline failure (HTTP 500)."""

    category = "ML"


class AIError(InsightFlowError):
    """AI Copilot failure (HTTP 500)."""

    category = "AI"


class InfrastructureError(InsightFlowError):
    """Database / Redis / storage failure (HTTP 503)."""

    category = "INFRASTRUCTURE"


class ExternalServiceError(InsightFlowError):
    """LLM provider or external API failure (HTTP 502)."""

    category = "EXTERNAL_SERVICE"
