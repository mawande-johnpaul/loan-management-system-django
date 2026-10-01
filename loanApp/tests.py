"""
BASELINE (characterization) tests for the ORIGINAL loanApp code, before the SOLID refactor.

- Self-contained: no factories.py, services.py, selectors.py or LoanStatus needed.
- Every test here should PASS on the original code.
- Classes ending in "KnownBugTests" pin CURRENT BUGGY behaviour. They are EXPECTED
  to fail after the refactor (that is the point: the failure shows the bug is fixed).
  Everything else should keep passing after the refactor.

Run:  python manage.py test loanApp
"""
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.urls import get_resolver, reverse

from loanApp import views
from loanApp.models import CustomerLoan, loanCategory, loanRequest, loanTransaction
from loginApp.models import CustomerSignUp

# URL names that are known to exist in your project.
HOME = "home"
USER_DASHBOARD = "loanApp:user_dashboard"
LOAN_REQUEST = "loanApp:loan_request"

# EDIT if your forms use different field names.
LOAN_REQUEST_POST = {"reason": "school fees", "amount": 1000, "year": 2}   # + category added below
PAYMENT_POST = {"payment": 100}

PASSWORD = "pass12345"

# Templates use {% static %}; the manifest storage needs collectstatic. Not needed in tests.
NO_MANIFEST = override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def url_for(view):
    """Find a view's URL by scanning the URLconf, so no URL names are needed."""
    def walk(patterns, prefix):
        for p in patterns:
            route = prefix + str(p.pattern)
            if hasattr(p, "url_patterns"):
                found = walk(p.url_patterns, route)
                if found:
                    return found
            elif p.callback is view:
                return "/" + route
        return None

    url = walk(get_resolver().url_patterns, "")
    assert url, f"No URL found for {view.__name__}"
    return url


def make_user(username="jane", **extra):
    return User.objects.create_user(username=username, password=PASSWORD, **extra)


def make_customer(username="jane"):
    return CustomerSignUp.objects.create(user=make_user(username))


def make_category():
    return loanCategory.objects.get_or_create(loan_name="Personal")[0]


def make_request(customer, amount=1000, year=2, status="pending"):
    return loanRequest.objects.create(
        customer=customer, category=make_category(),
        amount=amount, year=year, reason="test", status=status,
    )


def login_as(client, username="jane"):
    assert client.login(username=username, password=PASSWORD)


# --------------------------------------------------------------------------
@NO_MANIFEST
class HomeTests(TestCase):
    def test_home_is_public(self):
        self.assertEqual(self.client.get(reverse(HOME)).status_code, 200)


@NO_MANIFEST
class LoginRequiredTests(TestCase):
    def test_every_customer_view_redirects_anonymous_users(self):
        urls = {
            "loan_request": reverse(LOAN_REQUEST),
            "dashboard": reverse(USER_DASHBOARD),
            "payment": url_for(views.LoanPayment),
            "transactions": url_for(views.UserTransaction),
            "loan_history": url_for(views.UserLoanHistory),
        }
        for name, url in urls.items():
            with self.subTest(view=name):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/account/login-customer", resp["Location"])


# --------------------------------------------------------------------------
@NO_MANIFEST
class LoanRequestViewTests(TestCase):
    def setUp(self):
        self.customer = make_customer("jane")
        login_as(self.client)

    def test_page_loads_with_form(self):
        resp = self.client.get(reverse(LOAN_REQUEST))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)

    def test_valid_post_creates_pending_request_for_current_user(self):
        data = dict(LOAN_REQUEST_POST, category=make_category().pk)
        resp = self.client.post(reverse(LOAN_REQUEST), data)

        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        req = loanRequest.objects.get()
        self.assertEqual(req.customer, self.customer)
        self.assertEqual(req.amount, 1000)
        self.assertEqual(req.status, "pending")

    def test_invalid_post_creates_nothing_and_rerenders(self):
        resp = self.client.post(reverse(LOAN_REQUEST), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(loanRequest.objects.count(), 0)


@NO_MANIFEST
class LoanPaymentViewTests(TestCase):
    def setUp(self):
        self.customer = make_customer("jane")
        login_as(self.client)
        self.url = url_for(views.LoanPayment)

    def test_page_loads_with_form(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)

    def test_valid_post_records_payment_for_current_user(self):
        resp = self.client.post(self.url, PAYMENT_POST)
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        payment = loanTransaction.objects.get()
        self.assertEqual(payment.customer, self.customer)
        self.assertEqual(payment.payment, 100)

    def test_invalid_post_records_nothing(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(loanTransaction.objects.count(), 0)


@NO_MANIFEST
class CustomerListViewTests(TestCase):
    def setUp(self):
        self.jane = make_customer("jane")
        self.bob = make_customer("bob")
        login_as(self.client, "jane")

    def test_transactions_show_only_own(self):
        loanTransaction.objects.create(customer=self.jane, payment=10)
        loanTransaction.objects.create(customer=self.bob, payment=20)
        resp = self.client.get(url_for(views.UserTransaction))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([t.customer for t in resp.context["transactions"]], [self.jane])

    def test_loan_history_shows_only_own(self):
        make_request(self.jane)
        make_request(self.bob)
        make_request(self.bob)
        resp = self.client.get(url_for(views.UserLoanHistory))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["loans"]), 1)


@NO_MANIFEST
class UserDashboardTests(TestCase):
    def setUp(self):
        self.jane = make_customer("jane")
        self.bob = make_customer("bob")
        login_as(self.client, "jane")

    def test_counts_only_own_requests_by_status(self):
        make_request(self.jane, status="pending")
        make_request(self.jane, status="approved")
        make_request(self.jane, status="rejected")
        make_request(self.bob, status="approved")
        make_request(self.bob, status="approved")

        resp = self.client.get(reverse(USER_DASHBOARD))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["request"], 3)      # all of jane's requests
        self.assertEqual(resp.context["approved"], 1)
        self.assertEqual(resp.context["rejected"], 1)

    def test_sums_only_own_loan_and_payments(self):
        CustomerLoan.objects.create(customer=self.jane, total_loan=1000, payable_loan=1240)
        CustomerLoan.objects.create(customer=self.bob, total_loan=999, payable_loan=999)
        loanTransaction.objects.create(customer=self.jane, payment=100)
        loanTransaction.objects.create(customer=self.jane, payment=50)
        loanTransaction.objects.create(customer=self.bob, payment=77)

        resp = self.client.get(reverse(USER_DASHBOARD))

        self.assertEqual(resp.context["totalLoan"], 1000)
        self.assertEqual(resp.context["totalPayable"], 1240)
        self.assertEqual(resp.context["totalPaid"], 150)


# --------------------------------------------------------------------------
# KNOWN BUGS: these assert the CURRENT (wrong) behaviour and should flip after the refactor.
# --------------------------------------------------------------------------
@NO_MANIFEST
class DashboardKnownBugTests(TestCase):
    def test_customer_without_data_gets_None_instead_of_zero(self):
        make_customer("jane")
        login_as(self.client)
        resp = self.client.get(reverse(USER_DASHBOARD))
        self.assertIsNone(resp.context["totalLoan"])        # refactor: 0
        self.assertIsNone(resp.context["totalPayable"])     # refactor: 0
        self.assertIsNone(resp.context["totalPaid"])        # refactor: 0
        self.assertEqual(resp.context["request"], 0)


@NO_MANIFEST
class NoProfileKnownBugTests(TestCase):
    """A logged-in user with no CustomerSignUp (e.g. staff) crashes customer views."""

    def setUp(self):
        make_user("boss", is_staff=True)
        login_as(self.client, "boss")

    def test_dashboard_crashes(self):                       # refactor: 404 or a redirect
        with self.assertRaises(ObjectDoesNotExist):
            self.client.get(reverse(USER_DASHBOARD))

    def test_loan_request_post_crashes(self):
        with self.assertRaises(ObjectDoesNotExist):
            data = dict(LOAN_REQUEST_POST, category=make_category().pk)
            self.client.post(reverse(LOAN_REQUEST), data)


@NO_MANIFEST
class NotFoundPageKnownBugTests(TestCase):
    def test_unknown_url_shows_not_found_page_with_status_200(self):
        resp = self.client.get("/this/url/does/not/exist/")
        self.assertEqual(resp.status_code, 200)             # refactor: 404