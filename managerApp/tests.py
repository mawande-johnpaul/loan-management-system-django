"""
managerApp tests. Written against the REFACTORED views from the SOLID report
(POST-only approve/reject/remove, services + selectors, named URLs).

Run:  python manage.py test managerApp
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from loanApp.factories import (
    DEFAULT_PASSWORD,
    make_customer,
    make_customer_loan,
    make_loan_request,
    make_payment,
    make_user,
)
from loanApp.models import CustomerLoan, LoanStatus, loanRequest
from loginApp.models import CustomerSignUp

# EDIT: URL names from your managerApp/urls.py.
DASHBOARD = "managerApp:dashboard"
APPROVE = "managerApp:approved_request"      # takes id
REJECT = "managerApp:rejected_request"       # takes id
REMOVE_USER = "managerApp:user_remove"       # takes pk
ADMIN_LOGIN_PATH = "/manager/admin-login/"

def make_staff(username="boss"):
    return make_user(username, is_staff=True)


class StaffAccessTests(TestCase):
    def test_anonymous_is_sent_to_admin_login(self):
        resp = self.client.get(reverse(DASHBOARD))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(ADMIN_LOGIN_PATH, resp["Location"])

    def test_normal_customer_cannot_open_dashboard(self):
        make_customer("jane")
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        resp = self.client.get(reverse(DASHBOARD))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(ADMIN_LOGIN_PATH, resp["Location"])

    def test_staff_can_open_dashboard(self):
        make_staff()
        self.client.login(username="boss", password=DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse(DASHBOARD)).status_code, 200)


class DashboardTests(TestCase):
    def setUp(self):
        make_staff()
        self.client.login(username="boss", password=DEFAULT_PASSWORD)

    def test_empty_system_shows_zeros(self):
        resp = self.client.get(reverse(DASHBOARD))
        for key in ("totalCustomer", "request", "approved", "rejected",
                    "totalLoan", "totalPayable", "totalPaid"):
            self.assertEqual(resp.context[key], 0, msg=key)

    def test_dashboard_aggregates_across_all_customers(self):
        jane = make_customer("jane")
        bob = make_customer("bob")
        make_loan_request(jane, status=LoanStatus.PENDING)
        make_loan_request(jane, status=LoanStatus.APPROVED)
        make_loan_request(bob, status=LoanStatus.REJECTED)
        make_customer_loan(jane, total_loan=1000, payable_loan=1240)
        make_customer_loan(bob, total_loan=500, payable_loan=560)
        make_payment(jane, payment=200)

        resp = self.client.get(reverse(DASHBOARD))
        self.assertEqual(resp.context["totalCustomer"], 2)
        self.assertEqual(resp.context["request"], 1)   # admin: pending count
        self.assertEqual(resp.context["approved"], 1)
        self.assertEqual(resp.context["rejected"], 1)
        self.assertEqual(resp.context["totalLoan"], 1500)
        self.assertEqual(resp.context["totalPayable"], 1800)
        self.assertEqual(resp.context["totalPaid"], 200)


class ApproveRejectViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = make_customer("jane")

    def setUp(self):
        make_staff()
        self.client.login(username="boss", password=DEFAULT_PASSWORD)
        self.req = make_loan_request(self.customer, amount=1000, year=2)

    def test_approve_rejects_get(self):
        resp = self.client.get(reverse(APPROVE, args=[self.req.id]))
        self.assertEqual(resp.status_code, 405)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, LoanStatus.PENDING)

    def test_approve_post_approves_and_credits_account(self):
        self.client.post(reverse(APPROVE, args=[self.req.id]))

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, LoanStatus.APPROVED)
        account = CustomerLoan.objects.get(customer=self.customer)
        self.assertEqual(account.total_loan, 1000)
        self.assertEqual(account.payable_loan, 1240)

    def test_approve_twice_does_not_double_the_loan(self):
        url = reverse(APPROVE, args=[self.req.id])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(CustomerLoan.objects.get(customer=self.customer).total_loan, 1000)

    def test_approve_unknown_id_is_404(self):
        resp = self.client.post(reverse(APPROVE, args=[999999]))
        self.assertEqual(resp.status_code, 404)

    def test_reject_rejects_get(self):
        resp = self.client.get(reverse(REJECT, args=[self.req.id]))
        self.assertEqual(resp.status_code, 405)

    def test_reject_post_rejects_without_creating_loan(self):
        self.client.post(reverse(REJECT, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, LoanStatus.REJECTED)
        self.assertFalse(CustomerLoan.objects.filter(customer=self.customer).exists())

    def test_non_staff_cannot_approve(self):
        self.client.logout()
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        self.client.post(reverse(APPROVE, args=[self.req.id]))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, LoanStatus.PENDING)


class UserRemoveTests(TestCase):
    def setUp(self):
        make_staff()
        self.client.login(username="boss", password=DEFAULT_PASSWORD)

    def test_remove_rejects_get(self):
        customer = make_customer("jane")
        resp = self.client.get(reverse(REMOVE_USER, args=[customer.pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(CustomerSignUp.objects.filter(pk=customer.pk).exists())

    def test_remove_deletes_the_customer_and_its_own_user(self):
        customer = make_customer("jane")
        user_id = customer.user_id
        self.client.post(reverse(REMOVE_USER, args=[customer.pk]))

        self.assertFalse(CustomerSignUp.objects.filter(pk=customer.pk).exists())
        self.assertFalse(User.objects.filter(pk=user_id).exists())

    def test_remove_never_deletes_a_different_user_when_ids_differ(self):
        # Regression for the original bug: it reused the customer pk as the User pk.
        # Extra users make User ids diverge from CustomerSignUp ids.
        for i in range(3):
            make_user(f"filler{i}")
        target = make_customer("jane")
        bystander = make_customer("bob")
        self.assertNotEqual(target.pk, target.user_id)  # ids really differ

        self.client.post(reverse(REMOVE_USER, args=[target.pk]))

        self.assertFalse(User.objects.filter(username="jane").exists())
        self.assertTrue(User.objects.filter(username="bob").exists())
        self.assertTrue(CustomerSignUp.objects.filter(pk=bystander.pk).exists())
        self.assertEqual(User.objects.filter(username__startswith="filler").count(), 3)

    def test_remove_unknown_pk_is_404(self):
        resp = self.client.post(reverse(REMOVE_USER, args=[999999]))
        self.assertEqual(resp.status_code, 404)


class SuperuserLoginTests(TestCase):
    def test_superuser_login_redirects_to_dashboard(self):
        make_user("root", is_staff=True, is_superuser=True)
        resp = self.client.post(ADMIN_LOGIN_PATH, {"username": "root", "password": DEFAULT_PASSWORD})
        self.assertRedirects(resp, reverse(DASHBOARD), fetch_redirect_response=False)

    def test_non_superuser_is_refused_with_message(self):
        make_staff("boss")
        resp = self.client.post(ADMIN_LOGIN_PATH, {"username": "boss", "password": DEFAULT_PASSWORD})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["error"], "You are not Super User")

    def test_wrong_password_shows_an_error(self):
        # Fails on the ORIGINAL view (it returns no error when authenticate() is None).
        make_user("root", is_staff=True, is_superuser=True)
        resp = self.client.post(ADMIN_LOGIN_PATH, {"username": "root", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context.get("error"))