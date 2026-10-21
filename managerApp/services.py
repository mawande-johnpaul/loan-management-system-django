
from datetime import date

from django.contrib.auth.models import User

from loanApp.models import CustomerLoan, loanRequest
from loginApp.models import CustomerSignUp

from .constants import Loan, Status


def calculate_payable(amount, years):
    """
    Calculate principal and simple annual interest
    using the original application's formula.
    """
    amount = int(amount)
    years = int(years)

    return amount + (
        amount * Loan.ANNUAL_INTEREST_RATE * years
    )


def update_customer_balance(customer, amount, payable):
    """
    Update the balance of an existing customer.

    The original two-step update behavior is retained.
    """
    balance = CustomerLoan.objects.get(
        customer=customer
    )

    CustomerLoan.objects.filter(
        customer=customer
    ).update(
        total_loan=int(balance.total_loan) + amount
    )

    CustomerLoan.objects.filter(
        customer=customer
    ).update(
        payable_loan=int(balance.payable_loan) + payable
    )


def create_customer_balance(customer, amount, payable):
    """Create a loan balance for a new borrowing customer."""
    return CustomerLoan.objects.create(
        customer=customer,
        total_loan=amount,
        payable_loan=payable,
    )


def approve_loan_request(request_id):
    """
    Process approval using the original business rules.

    Existing status-transition behavior is retained
    to preserve compatibility with the baseline tests.
    """
    loan = loanRequest.objects.get(
        pk=request_id
    )

    loan.status_date = date.today().strftime(
        "%B %d, %Y"
    )
    loan.save()

    customer = loan.customer
    amount = int(loan.amount)
    payable = calculate_payable(
        amount,
        loan.year,
    )

    if CustomerLoan.objects.filter(
        customer=customer
    ).exists():
        update_customer_balance(
            customer,
            amount,
            payable,
        )
    else:
        create_customer_balance(
            customer,
            amount,
            payable,
        )

    loanRequest.objects.filter(
        pk=request_id
    ).update(
        status=Status.APPROVED
    )

    return loan


def reject_loan_request(request_id):
    """
    Process rejection using the original business rules.
    """
    loan = loanRequest.objects.get(
        pk=request_id
    )

    loan.status_date = date.today().strftime(
        "%B %d, %Y"
    )
    loan.save()

    loanRequest.objects.filter(
        pk=request_id
    ).update(
        status=Status.REJECTED
    )

    return loan


def remove_customer(customer_id):
    """
    Preserve the original customer deletion behavior.

    The existing assumption that the customer and
    auth user share a primary key is retained solely
    for behavior-preserving refactoring.
    """
    CustomerSignUp.objects.get(
        pk=customer_id
    ).delete()

    user = User.objects.get(
        pk=customer_id
    )
    user.delete()
