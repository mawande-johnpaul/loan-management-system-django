"""
loanApp tests. Written against the REFACTORED code from the SOLID report
(loanApp/services.py, loanApp/selectors.py, LoanStatus in models.py).

Run:  python manage.py test loanApp
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import selectors, services
from .factories import (
    DEFAULT_PASSWORD,
    make_customer,
    make_customer_loan,
    make_loan_request,
    make_payment,
)
from .models import CustomerLoan, LoanStatus

# EDIT: URL names from your loanApp/urls.py.
USER_DASHBOARD_URL = "loanApp:user_dashboard"
LOAN_REQUEST_URL = "loanApp:loan_request"


# --------------------------------------------------------------------------
# Pure logic: no database needed
# --------------------------------------------------------------------------
class CalculatePayableTests(SimpleTestCase):
    def test_simple_interest_two_years(self):
        self.assertEqual(services.calculate_payable(1000, 2), Decimal("1240"))

    def test_zero_years_returns_principal(self):
        self.assertEqual(services.calculate_payable(1000, 0), Decimal("1000"))

    def test_custom_rate(self):
        self.assertEqual(
            services.calculate_payable(1000, 1, rate=Decimal("0.05")), Decimal("1050")
        )

    def test_accepts_string_amount_and_year(self):
        self.assertEqual(services.calculate_payable("1000", "2"), Decimal("1240"))

    def test_no_float_rounding_error(self):
        # The old code used 0.12 as a float. Decimal keeps this exact.
        self.assertEqual(services.calculate_payable(100, 3), Decimal("136.00"))


class LoanStatusTests(SimpleTestCase):
    def test_values_match_legacy_strings(self):
        # Existing rows in the database use these literal strings.
        self.assertEqual(LoanStatus.PENDING, "pending")
        self.assertEqual(LoanStatus.APPROVED, "approved")
        self.assertEqual(LoanStatus.REJECTED, "rejected")


# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------
class ApproveLoanServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = make_customer("jane")

    def test_first_approval_creates_customer_loan(self):
        req = make_loan_request(self.customer, amount=1000, year=2)
        services.approve_loan(req, today=date(2026, 1, 15))

        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(account.total_loan, 1000)
        self.assertEqual(account.payable_loan, 1240)

    def test_approval_sets_status_and_date(self):
        req = make_loan_request(self.customer)
        services.approve_loan(req, today=date(2026, 1, 15))

        req.refresh_from_db()
        self.assertEqual(req.status, LoanStatus.APPROVED)
        self.assertEqual(str(req.status_date), "2026-01-15")

    def test_second_approval_accumulates_on_existing_account(self):
        services.approve_loan(make_loan_request(self.customer, amount=1000, year=2))
        services.approve_loan(make_loan_request(self.customer, amount=500, year=1))

        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(account.total_loan, 1500)
        self.assertEqual(account.payable_loan, 1240 + 560)
        self.assertEqual(CustomerLoan.objects.filter(customer=self.customer).count(), 1)

    def test_double_approval_is_refused(self):
        req = make_loan_request(self.customer)
        services.approve_loan(req)

        with self.assertRaises(ValueError):
            services.approve_loan(req)

        self.assertEqual(CustomerLoan.objects.get(customer=self.customer).total_loan, 1000)

    def test_rejected_request_cannot_be_approved(self):
        req = make_loan_request(self.customer, status=LoanStatus.REJECTED)
        with self.assertRaises(ValueError):
            services.approve_loan(req)
        self.assertFalse(CustomerLoan.objects.filter(customer=self.customer).exists())

    def test_failure_midway_rolls_back_everything(self):
        req = make_loan_request(self.customer)
        with mock.patch.object(CustomerLoan, "save", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.approve_loan(req)

        req.refresh_from_db()
        self.assertEqual(req.status, LoanStatus.PENDING)
        self.assertFalse(CustomerLoan.objects.filter(customer=self.customer).exists())


class RejectLoanServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = make_customer("jane")

    def test_reject_sets_status_and_date_without_touching_balance(self):
        req = make_loan_request(self.customer)
        services.reject_loan(req, today=date(2026, 2, 1))

        req.refresh_from_db()
        self.assertEqual(req.status, LoanStatus.REJECTED)
        self.assertEqual(str(req.status_date), "2026-02-01")
        self.assertFalse(CustomerLoan.objects.filter(customer=self.customer).exists())

    def test_cannot_reject_twice(self):
        req = make_loan_request(self.customer)
        services.reject_loan(req)
        with self.assertRaises(ValueError):
            services.reject_loan(req)

    def test_cannot_reject_an_approved_request(self):
        req = make_loan_request(self.customer, status=LoanStatus.APPROVED)
        with self.assertRaises(ValueError):
            services.reject_loan(req)


# --------------------------------------------------------------------------
# Selectors
# --------------------------------------------------------------------------
class GetLoanStatsTests(TestCase):
    def test_empty_database_returns_zeros_not_none(self):
        stats = selectors.get_loan_stats()
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["total_loan"], 0)
        self.assertEqual(stats["total_payable"], 0)
        self.assertEqual(stats["total_paid"], 0)

    def test_counts_by_status(self):
        c = make_customer("jane")
        make_loan_request(c, status=LoanStatus.PENDING)
        make_loan_request(c, status=LoanStatus.PENDING)
        make_loan_request(c, status=LoanStatus.APPROVED)
        make_loan_request(c, status=LoanStatus.REJECTED)

        stats = selectors.get_loan_stats()
        self.assertEqual(stats["total_requests"], 4)
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["approved"], 1)
        self.assertEqual(stats["rejected"], 1)

    def test_sums_loans_and_payments(self):
        c = make_customer("jane")
        make_customer_loan(c, total_loan=1000, payable_loan=1240)
        make_payment(c, payment=100)
        make_payment(c, payment=50)

        stats = selectors.get_loan_stats()
        self.assertEqual(stats["total_loan"], 1000)
        self.assertEqual(stats["total_payable"], 1240)
        self.assertEqual(stats["total_paid"], 150)

    def test_customer_filter_isolates_one_customer(self):
        jane = make_customer("jane")
        bob = make_customer("bob")
        make_loan_request(jane, status=LoanStatus.APPROVED)
        make_loan_request(bob, status=LoanStatus.APPROVED)
        make_loan_request(bob, status=LoanStatus.REJECTED)
        make_customer_loan(bob, total_loan=999, payable_loan=999)
        make_payment(bob, payment=77)

        stats = selectors.get_loan_stats(customer=jane)
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["rejected"], 0)
        self.assertEqual(stats["total_loan"], 0)
        self.assertEqual(stats["total_paid"], 0)

    def test_customer_with_no_data_gets_zeros(self):
        stats = selectors.get_loan_stats(customer=make_customer("newbie"))
        self.assertEqual(stats["total_loan"], 0)
        self.assertEqual(stats["total_paid"], 0)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------
class HomeViewTests(TestCase):
    def test_home_is_public(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)


class CustomerViewAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = make_customer("jane")

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse(USER_DASHBOARD_URL))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_loan_request_requires_login(self):
        resp = self.client.get(reverse(LOAN_REQUEST_URL))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_dashboard_shows_only_own_numbers(self):
        other = make_customer("bob")
        make_loan_request(self.customer, status=LoanStatus.APPROVED)
        make_loan_request(other, status=LoanStatus.APPROVED)
        make_loan_request(other, status=LoanStatus.APPROVED)

        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        resp = self.client.get(reverse(USER_DASHBOARD_URL))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["approved"], 1)
        self.assertEqual(resp.context["request"], 1)

    def test_dashboard_for_customer_without_data_does_not_show_none(self):
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        resp = self.client.get(reverse(USER_DASHBOARD_URL))
        self.assertEqual(resp.context["totalLoan"], 0)
        self.assertEqual(resp.context["totalPaid"], 0)