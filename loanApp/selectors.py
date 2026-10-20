# loanApp/selectors.py
from django.db.models import Count, Q, Sum

from .models import CustomerLoan, LoanStatus, loanRequest, loanTransaction

from enum import Enum

class Totals(str, Enum):
    TOTAL_LOAN = "total_loan"
    TOTAL_PAYABLE = "total_payable"
    TOTAL_PAID = "total_paid"

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
        "total_loan": sums.get(Totals.TOTAL_LOAN) or 0,
        "total_payable": sums.get(Totals.TOTAL_PAYABLE) or 0,
        "total_paid": paid.get(Totals.TOTAL_PAID) or 0,
    }