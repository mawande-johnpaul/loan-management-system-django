"""
Shared test helpers. Every model field guess lives here, so if your models differ
you only need to edit THIS file, not every test.

Place at: loanApp/factories.py
"""
from django.contrib.auth.models import User

from loginApp.models import CustomerSignUp
from loanApp.models import (
    CustomerLoan,
    LoanStatus,
    loanCategory,
    loanRequest,
    loanTransaction,
)

DEFAULT_PASSWORD = "pass12345"


def make_user(username="jane", password=DEFAULT_PASSWORD, **extra):
    return User.objects.create_user(username=username, password=password, **extra)


def make_customer(username="jane"):
    return CustomerSignUp.objects.create(user=make_user(username))


def make_category(**overrides):
    data = {"loan_name": "Personal"}
    data.update(overrides)
    return loanCategory.objects.create(**data)


def make_loan_request(customer, amount=1000, year=2, status=LoanStatus.PENDING,
                      category=None, **extra):
    # EDIT: add any other required loanRequest fields here.
    return loanRequest.objects.create(
        customer=customer,
        category=category or make_category(),
        amount=amount,
        year=year,
        reason="test",
        status=status,
        **extra,
    )


def make_customer_loan(customer, total_loan=1000, payable_loan=1240):
    return CustomerLoan.objects.create(
        customer=customer, total_loan=total_loan, payable_loan=payable_loan
    )


def make_payment(customer, payment=100):
    # EDIT: add any other required loanTransaction fields here.
    return loanTransaction.objects.create(customer=customer, payment=payment)