"""
BASELINE (characterization) tests for the ORIGINAL managerApp code, before the SOLID refactor.

- Self-contained: no factories.py, services.py, selectors.py or LoanStatus needed.
- Every test here should PASS on the original code.
- Classes ending in "KnownBugTests" pin CURRENT BUGGY behaviour. They are EXPECTED
  to fail after the refactor (that is the point: the failure shows the bug is fixed).
  Note: approve/reject/remove become POST-only after the refactor, so the tests that
  use POST keep passing and only the "GET still works" bug tests flip.

Run:  python manage.py test managerApp
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import get_resolver, reverse

from loanApp.models import CustomerLoan, loanCategory, loanRequest, loanTransaction
from loginApp.models import CustomerSignUp
from managerApp import views

DASHBOARD = "managerApp:dashboard"
ADMIN_LOGIN = "managerApp:admin-login"
APPROVE = "managerApp:approved_request"      # takes id
REJECT = "managerApp:rejected_request"       # takes id
REMOVE_USER = "managerApp:user_remove"       # takes pk

# EDIT if LoanCategoryForm uses a different field name.
CATEGORY_POST = {"loan_name": "Business"}

PASSWORD = "pass12345"

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


def make_request(customer, amount=1000, year=2, status="pending"):
    category = loanCategory.objects.get_or_create(loan_name="Personal")[0]
    return loanRequest.objects.create(
        customer=customer, category=category,
        amount=amount, year=year, reason="test", status=status,
    )


def login_as(client, username):
    assert client.login(username=username, password=PASSWORD)


def login_staff(client, username="boss"):
    make_user(username, is_staff=True)
    login_as(client, username)


# --------------------------------------------------------------------------
@NO_MANIFEST
class StaffAccessTests(TestCase):
    def staff_urls(self):
        return {
            "dashboard": reverse(DASHBOARD),
            "add_category": url_for(views.add_category),
            "total_users": url_for(views.total_users),
            "loan_request": url_for(views.loan_request),
            "approved_loan": url_for(views.approved_loan),
            "rejected_loan": url_for(views.rejected_loan),
            "transaction_loan": url_for(views.transaction_loan),
        }

    def test_anonymous_is_sent_to_admin_login(self):
        for name, url in self.staff_urls().items():
            with self.subTest(view=name):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/manager/admin-login", resp["Location"])

    def test_normal_customer_is_sent_to_admin_login(self):
        make_customer("jane")
        login_as(self.client, "jane")
        for name, url in self.staff_urls().items():
            with self.subTest(view=name):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/manager/admin-login", resp["Location"])

    def test_staff_can_open_every_page(self):
        login_staff(self.client)
        for name, url in self.staff_urls().items():
            with self.subTest(view=name):
                self.assertEqual(self.client.get(url).status_code, 200)


@NO_MANIFEST
class SuperuserLoginTests(TestCase):
    def test_page_loads(self):
        self.assertEqual(self.client.get(reverse(ADMIN_LOGIN)).status_code, 200)

    def test_superuser_login_redirects_to_dashboard(self):
        make_user("root", is_staff=True, is_superuser=True)
        resp = self.client.post(reverse(ADMIN_LOGIN), {"username": "root", "password": PASSWORD})
        self.assertRedirects(resp, reverse(DASHBOARD), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_staff_who_is_not_superuser_is_refused_with_message(self):
        make_user("boss", is_staff=True)
        resp = self.client.post(reverse(ADMIN_LOGIN), {"username": "boss", "password": PASSWORD})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["error"], "You are not Super User")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blank_form_shows_error(self):
        resp = self.client.post(reverse(ADMIN_LOGIN), {})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Invalid Username or Password", resp.context["error"])

    def test_wrong_password_does_not_log_in(self):
        make_user("root", is_staff=True, is_superuser=True)
        resp = self.client.post(reverse(ADMIN_LOGIN), {"username": "root", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_already_logged_in_user_is_redirected_home(self):
        make_customer("jane")
        login_as(self.client, "jane")
        resp = self.client.get(reverse(ADMIN_LOGIN))
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)


@NO_MANIFEST
class DashboardTests(TestCase):
    def setUp(self):
        login_staff(self.client)

    def test_aggregates_across_all_customers(self):
        jane = make_customer("jane")
        bob = make_customer("bob")
        make_request(jane, status="pending")
        make_request(jane, status="approved")
        make_request(bob, status="rejected")
        CustomerLoan.objects.create(customer=jane, total_loan=1000, payable_loan=1240)
        CustomerLoan.objects.create(customer=bob, total_loan=500, payable_loan=560)
        loanTransaction.objects.create(customer=jane, payment=200)

        resp = self.client.get(reverse(DASHBOARD))

        self.assertEqual(resp.context["totalCustomer"], 2)
        self.assertEqual(resp.context["request"], 1)       # admin dashboard: pending count
        self.assertEqual(resp.context["approved"], 1)
        self.assertEqual(resp.context["rejected"], 1)
        self.assertEqual(resp.context["totalLoan"], 1500)
        self.assertEqual(resp.context["totalPayable"], 1800)
        self.assertEqual(resp.context["totalPaid"], 200)


@NO_MANIFEST
class AddCategoryTests(TestCase):
    def setUp(self):
        login_staff(self.client)

    def test_valid_post_creates_category_and_redirects_to_dashboard(self):
        resp = self.client.post(url_for(views.add_category), CATEGORY_POST)
        self.assertRedirects(resp, reverse(DASHBOARD), fetch_redirect_response=False)
        self.assertEqual(loanCategory.objects.count(), 1)

    def test_invalid_post_creates_nothing(self):
        resp = self.client.post(url_for(views.add_category), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(loanCategory.objects.count(), 0)


@NO_MANIFEST
class LoanListTests(TestCase):
    def setUp(self):
        login_staff(self.client)
        self.customer = make_customer("jane")

    def test_pending_page_lists_only_pending(self):
        make_request(self.customer, status="pending")
        make_request(self.customer, status="approved")
        resp = self.client.get(url_for(views.loan_request))
        self.assertEqual(len(resp.context["loanrequest"]), 1)

    def test_approved_page_lists_only_approved(self):
        make_request(self.customer, status="pending")
        make_request(self.customer, status="approved")
        resp = self.client.get(url_for(views.approved_loan))
        self.assertEqual(len(resp.context["approvedLoan"]), 1)

    def test_rejected_page_lists_only_rejected(self):
        make_request(self.customer, status="rejected")
        make_request(self.customer, status="approved")
        resp = self.client.get(url_for(views.rejected_loan))
        self.assertEqual(len(resp.context["rejectedLoan"]), 1)

    def test_transactions_page_lists_everyones_payments(self):
        loanTransaction.objects.create(customer=self.customer, payment=10)
        loanTransaction.objects.create(customer=make_customer("bob"), payment=20)
        resp = self.client.get(url_for(views.transaction_loan))
        self.assertEqual(len(resp.context["transactions"]), 2)

    def test_users_page_lists_customers(self):
        make_customer("bob")
        resp = self.client.get(url_for(views.total_users))
        self.assertEqual(len(resp.context["users"]), 2)


# --------------------------------------------------------------------------
@NO_MANIFEST
class ApproveRejectTests(TestCase):
    def setUp(self):
        login_staff(self.client)
        self.customer = make_customer("jane")
        self.req = make_request(self.customer, amount=1000, year=2)

    def test_approve_marks_request_and_creates_customer_loan(self):
        resp = self.client.post(reverse(APPROVE, args=[self.req.id]))

        self.assertEqual(resp.status_code, 200)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "approved")
        self.assertEqual(self.req.status_date, date.today().strftime("%B %d, %Y"))
        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(account.total_loan, 1000)
        self.assertEqual(account.payable_loan, 1240)        # 1000 + 12% x 2 years

    def test_approve_returns_pending_list_without_the_approved_one(self):
        resp = self.client.post(reverse(APPROVE, args=[self.req.id]))
        self.assertEqual(len(resp.context["loanrequest"]), 0)

    def test_second_approved_loan_accumulates_on_existing_account(self):
        second = make_request(self.customer, amount=1000, year=1)
        self.client.post(reverse(APPROVE, args=[self.req.id]))
        self.client.post(reverse(APPROVE, args=[second.id]))

        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(CustomerLoan.objects.filter(customer=self.customer).count(), 1)
        self.assertEqual(account.total_loan, 2000)
        self.assertEqual(account.payable_loan, 1240 + 1120)

    def test_reject_marks_request_without_creating_loan(self):
        self.client.post(reverse(REJECT, args=[self.req.id]))

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "rejected")
        self.assertEqual(self.req.status_date, date.today().strftime("%B %d, %Y"))
        self.assertFalse(CustomerLoan.objects.filter(customer=self.customer).exists())

    def test_non_staff_cannot_approve(self):
        self.client.logout()
        login_as(self.client, "jane")
        self.client.post(reverse(APPROVE, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "pending")


@NO_MANIFEST
class ApproveRejectKnownBugTests(TestCase):
    def setUp(self):
        login_staff(self.client)
        self.customer = make_customer("jane")
        self.req = make_request(self.customer, amount=1000, year=2)

    def test_approving_twice_credits_the_loan_twice(self):
        url = reverse(APPROVE, args=[self.req.id])
        self.client.post(url)
        self.client.post(url)
        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(account.total_loan, 2000)          # refactor: 1000

    def test_approved_request_can_be_rejected_afterwards(self):
        self.client.post(reverse(APPROVE, args=[self.req.id]))
        self.client.post(reverse(REJECT, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "rejected")       # refactor: stays "approved"
        self.assertEqual(CustomerLoan.objects.get(customer=self.customer).total_loan, 1000)

    def test_get_request_changes_state(self):
        self.client.get(reverse(APPROVE, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "approved")       # refactor: GET gives 405

    def test_get_request_can_reject(self):
        self.client.get(reverse(REJECT, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "rejected")       # refactor: GET gives 405

    def test_unknown_id_crashes_instead_of_404(self):
        with self.assertRaises(loanRequest.DoesNotExist):
            self.client.post(reverse(APPROVE, args=[999999]))   # refactor: 404
        with self.assertRaises(loanRequest.DoesNotExist):
            self.client.post(reverse(REJECT, args=[999999]))


# --------------------------------------------------------------------------
@NO_MANIFEST
class UserRemoveTests(TestCase):
    def setUp(self):
        login_staff(self.client)

    def test_remove_deletes_the_customer_profile_and_redirects_to_users(self):
        customer = make_customer("jane")
        resp = self.client.post(reverse(REMOVE_USER, args=[customer.pk]))
        self.assertRedirects(resp, "/manager/users", fetch_redirect_response=False)
        self.assertFalse(CustomerSignUp.objects.filter(pk=customer.pk).exists())


@NO_MANIFEST
class UserRemoveKnownBugTests(TestCase):
    def setUp(self):
        login_staff(self.client, "boss")                    # boss gets user id 1

    def test_remove_uses_customer_pk_as_user_pk(self):
        # jane's profile has pk 1, but her User has id 2. The view deletes User(id=1),
        # which is the staff user, and leaves jane's own User behind.
        customer = make_customer("jane")
        self.assertNotEqual(customer.pk, customer.user_id)

        self.client.post(reverse(REMOVE_USER, args=[customer.pk]))

        self.assertFalse(CustomerSignUp.objects.filter(pk=customer.pk).exists())
        self.assertTrue(User.objects.filter(username="jane").exists())   # refactor: False
        self.assertFalse(User.objects.filter(username="boss").exists())  # refactor: True

    def test_get_request_deletes(self):
        customer = make_customer("jane")
        self.client.get(reverse(REMOVE_USER, args=[customer.pk]))
        self.assertFalse(CustomerSignUp.objects.filter(pk=customer.pk).exists())  # refactor: 405

    def test_unknown_pk_crashes_instead_of_404(self):
        with self.assertRaises(CustomerSignUp.DoesNotExist):
            self.client.post(reverse(REMOVE_USER, args=[999999]))   # refactor: 404


@NO_MANIFEST
class DashboardKnownBugTests(TestCase):
    def test_empty_system_gets_None_instead_of_zero_for_money(self):
        login_staff(self.client)
        resp = self.client.get(reverse(DASHBOARD))
        self.assertEqual(resp.context["totalCustomer"], 0)
        self.assertEqual(resp.context["request"], 0)
        self.assertIsNone(resp.context["totalLoan"])        # refactor: 0
        self.assertIsNone(resp.context["totalPayable"])     # refactor: 0
        self.assertIsNone(resp.context["totalPaid"])        # refactor: 0