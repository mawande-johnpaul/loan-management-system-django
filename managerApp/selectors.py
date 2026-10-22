
from django.db.models import Sum

from loanApp.models import (
    CustomerLoan,
    loanRequest,
    loanTransaction,
)
from loginApp.models import CustomerSignUp

from .constants import Status


def get_objects(model, **filters):
    return model.objects.filter(**filters)


def get_object_count(model, **filters):
    return get_objects(model, **filters).count()


def get_total(model, field):
    return model.objects.aggregate(
        total=Sum(field)
    )["total"]


def get_dashboard_statistics():
    """
    Retrieve dashboard statistics while preserving
    the original template context keys and values.
    """
    return {
        "totalCustomer": get_object_count(
            CustomerSignUp
        ),
        "request": get_object_count(
            loanRequest,
            status=Status.PENDING,
        ),
        "approved": get_object_count(
            loanRequest,
            status=Status.APPROVED,
        ),
        "rejected": get_object_count(
            loanRequest,
            status=Status.REJECTED,
        ),
        "totalLoan": get_total(
            CustomerLoan,
            "total_loan",
        ),
        "totalPayable": get_total(
            CustomerLoan,
            "payable_loan",
        ),
        "totalPaid": get_total(
            loanTransaction,
            "payment",
        ),
    }
