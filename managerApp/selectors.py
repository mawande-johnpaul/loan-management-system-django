from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.signals import post_delete, post_save

from loanApp.models import CustomerLoan, loanRequest, loanTransaction
from loginApp.models import CustomerSignUp

from .constants import Cache, Status
from .contracts import must_return_all_statistics


def get_objects(model, related=(), **filters):
    queryset = model.objects.filter(**filters)
    # select_related() with no arguments follows every FK, so only call it when asked.
    return queryset.select_related(*related) if related else queryset


def get_object_count(model, **filters):
    return get_objects(model, **filters).count()


def get_total(model, field):
    return model.objects.aggregate(total=Sum(field))["total"]


def get_request_counts():
    """The three status counts in one query instead of three."""
    counts = loanRequest.objects.aggregate(
        n_pending=Count("pk", filter=Q(status=Status.PENDING)),
        n_approved=Count("pk", filter=Q(status=Status.APPROVED)),
        n_rejected=Count("pk", filter=Q(status=Status.REJECTED)),
    )
    return {
        "request": counts["n_pending"],
        "approved": counts["n_approved"],
        "rejected": counts["n_rejected"],
    }


@must_return_all_statistics
def compute_dashboard_statistics():
    """Same template context keys and values as the original."""
    return {
        "totalCustomer": get_object_count(CustomerSignUp),
        **get_request_counts(),
        "totalLoan": get_total(CustomerLoan, "total_loan"),
        "totalPayable": get_total(CustomerLoan, "payable_loan"),
        "totalPaid": get_total(loanTransaction, "payment"),
    }


def get_dashboard_statistics():
    return cache.get_or_set(
        Cache.DASHBOARD_KEY, compute_dashboard_statistics, Cache.DASHBOARD_TTL
    )


def invalidate_dashboard_statistics(**_):
    cache.delete(Cache.DASHBOARD_KEY)


# Clear the cached dashboard whenever a model it summarises is saved or deleted.
# Connected at import time, so it does not depend on apps.py or INSTALLED_APPS.
for _model in (CustomerSignUp, loanRequest, CustomerLoan, loanTransaction):
    for _signal in (post_save, post_delete):
        _signal.connect(
            invalidate_dashboard_statistics,
            sender=_model,
            dispatch_uid="managerApp-dashboard-cache",
        )