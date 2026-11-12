"""Design-by-contract decorators for managerApp, declared here and applied with @."""
from functools import wraps

from django.core.exceptions import BadRequest

from loanApp.models import loanRequest

from .constants import Status

STATISTIC_KEYS = {
    "totalCustomer", "request", "approved", "rejected",
    "totalLoan", "totalPayable", "totalPaid",
}


class ContractViolation(BadRequest):
    """A contract was broken. Django answers BadRequest with HTTP 400."""


def requires(condition, message):
    """Precondition: condition(*args, **kwargs) must hold before the function runs."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not condition(*args, **kwargs):
                raise ContractViolation(message)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ensures(condition, message):
    """Postcondition: condition(result) must hold after the function returns."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not condition(result):
                raise ContractViolation(message)
            return result
        return wrapper
    return decorator


# ---- the contracts used in managerApp -------------------------------------------------
must_be_pending = requires(
    lambda request_id: not loanRequest.objects.filter(pk=request_id)
    .exclude(status=Status.PENDING).exists(),
    "Only a pending loan request can be approved or rejected.",
)

must_have_valid_terms = requires(
    lambda amount, years: int(amount) > 0 and int(years) >= 0,
    "Loan amount must be positive and years cannot be negative.",
)

must_return_non_negative = ensures(lambda result: result >= 0, "Result cannot be negative.")

must_return_all_statistics = ensures(
    lambda stats: STATISTIC_KEYS <= stats.keys(),
    "Dashboard statistics are missing keys the template needs.",
)


def must_return_status(*codes):
    return ensures(
        lambda response: response.status_code in codes,
        f"View must respond with status {codes}.",
    )