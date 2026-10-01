# loanApp/selectors.py
from django.db.models import Count, Q, Sum

from .models import CustomerLoan, LoanStatus, loanRequest, loanTransaction


def get_loan_stats(customer=None):
    requests = loanRequest.objects.all()
    accounts = CustomerLoan.objects.all()
    payments = loanTransaction.objects.all()
    if customer is not None:
        requests = requests.filter(customer=customer)
        accounts = accounts.filter(customer=customer)
        payments = payments.filter(customer=customer)

    counts = requests.aggregate(
        total_requests=Count("id"),
        pending=Count("id", filter=Q(status=LoanStatus.PENDING)),
        approved=Count("id", filter=Q(status=LoanStatus.APPROVED)),
        rejected=Count("id", filter=Q(status=LoanStatus.REJECTED)),
    )
    sums = accounts.aggregate(total_loan=Sum("total_loan"), total_payable=Sum("payable_loan"))
    paid = payments.aggregate(total_paid=Sum("payment"))
    return {
        **counts,
        "total_loan": sums["total_loan"] or 0,
        "total_payable": sums["total_payable"] or 0,
        "total_paid": paid["total_paid"] or 0,
    }