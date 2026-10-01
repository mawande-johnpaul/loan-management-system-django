# loanApp/services.py
from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import CustomerLoan, LoanStatus, loanRequest

DEFAULT_RATE = Decimal("0.12")


def calculate_payable(amount, years, rate=DEFAULT_RATE):
    amount = Decimal(str(amount))
    years = Decimal(str(years))
    return amount * (1 + rate * years)


def _to_decimal(value):
    return Decimal(str(value))


@transaction.atomic
def approve_loan(loan, today=None):
    today = today or date.today()
    locked = loanRequest.objects.select_for_update().get(pk=loan.pk)
    if locked.status != LoanStatus.PENDING:
        raise ValueError(f"Cannot approve a {locked.status} request")

    account, _ = CustomerLoan.objects.get_or_create(
        customer=locked.customer,
        defaults={"total_loan": 0, "payable_loan": 0},
    )
    account.total_loan = _to_decimal(account.total_loan) + _to_decimal(locked.amount)
    account.payable_loan = _to_decimal(account.payable_loan) + calculate_payable(
        locked.amount, locked.year
    )
    account.save()

    locked.status = LoanStatus.APPROVED
    locked.status_date = today.isoformat()
    locked.save()
    loan.status, loan.status_date = locked.status, locked.status_date
    return account


@transaction.atomic
def reject_loan(loan, today=None):
    today = today or date.today()
    locked = loanRequest.objects.select_for_update().get(pk=loan.pk)
    if locked.status != LoanStatus.PENDING:
        raise ValueError(f"Cannot reject a {locked.status} request")
    locked.status = LoanStatus.REJECTED
    locked.status_date = today.isoformat()
    locked.save()
    loan.status, loan.status_date = locked.status, locked.status_date