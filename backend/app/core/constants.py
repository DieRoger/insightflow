"""Centralized business constants.

No magic numbers anywhere in the codebase — business thresholds live here.
"""

# Risk classification thresholds (churn prediction)
HIGH_RISK_THRESHOLD: float = 0.7
MEDIUM_RISK_THRESHOLD: float = 0.3

# Customer lifecycle
NEW_CUSTOMER_DAYS: int = 90
AT_RISK_CHURN_SCORE: float = 0.6
SAFE_CHURN_SCORE: float = 0.4
CHURN_NO_USAGE_DAYS: int = 90

# Reviewer agent
MAX_REVIEW_RETRIES: int = 3
LOW_CONFIDENCE_THRESHOLD: float = 0.6
