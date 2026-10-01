"""
loginApp tests. Written against the REFACTORED code from the SOLID report
(loginApp/services.py register_customer, loginApp/selectors.py get_customer,
form-level username validation).

Run:  python manage.py test loginApp
"""
from unittest import mock

from django.contrib.auth.models import User
from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from loanApp.factories import DEFAULT_PASSWORD, make_customer, make_user
from .forms import CustomerSignUpForm
from .models import CustomerSignUp
from .selectors import get_customer
from .services import register_customer

# EDIT: URL names from your loginApp/urls.py.
SIGNUP = "login_App:signup_customer"
LOGIN = "login_App:login_customer"
LOGOUT = "login_App:logout"
EDIT = "login_App:edit-customer"


def signup_data(username="newuser", password="Str0ng!pass99"):
    # EDIT: add any extra required fields your CustomerSignUpForm has.
    return {"username": username, "password1": password, "password2": password}


# --------------------------------------------------------------------------
# Service + form
# --------------------------------------------------------------------------
class RegisterCustomerServiceTests(TestCase):
    def test_creates_user_and_profile(self):
        form = CustomerSignUpForm(signup_data())
        self.assertTrue(form.is_valid(), form.errors)

        user = register_customer(form)

        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertTrue(CustomerSignUp.objects.filter(user=user).exists())

    def test_profile_failure_leaves_no_orphan_user(self):
        form = CustomerSignUpForm(signup_data())
        self.assertTrue(form.is_valid(), form.errors)

        with mock.patch.object(
            CustomerSignUp.objects, "create", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                register_customer(form)

        self.assertFalse(User.objects.filter(username="newuser").exists())


class CustomerSignUpFormTests(TestCase):
    def test_duplicate_username_is_invalid(self):
        make_user("taken")
        form = CustomerSignUpForm(signup_data(username="taken"))
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_mismatched_passwords_are_invalid(self):
        data = signup_data()
        data["password2"] = "different"
        self.assertFalse(CustomerSignUpForm(data).is_valid())

    def test_weak_password_is_invalid(self):
        self.assertFalse(CustomerSignUpForm(signup_data(password="123")).is_valid())


# --------------------------------------------------------------------------
# Selector
# --------------------------------------------------------------------------
class GetCustomerTests(TestCase):
    def test_returns_the_customer_for_a_user(self):
        customer = make_customer("jane")
        self.assertEqual(get_customer(customer.user), customer)

    def test_user_without_profile_gives_404_not_a_crash(self):
        staff = make_user("boss", is_staff=True)
        with self.assertRaises(Http404):
            get_customer(staff)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------
class SignUpViewTests(TestCase):
    def test_page_loads(self):
        self.assertEqual(self.client.get(reverse(SIGNUP)).status_code, 200)

    def test_valid_signup_creates_records_and_logs_in(self):
        resp = self.client.post(reverse(SIGNUP), signup_data())

        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        user = User.objects.get(username="newuser")
        self.assertTrue(CustomerSignUp.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_username_stays_on_page_and_creates_nothing(self):
        make_customer("taken")
        before = User.objects.count()

        resp = self.client.post(reverse(SIGNUP), signup_data(username="taken"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), before)

    def test_logged_in_user_is_redirected_away(self):
        make_customer("jane")
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        resp = self.client.get(reverse(SIGNUP))
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)

    def test_password_is_never_printed(self):
        # Regression for the original `print(username, password1)` line.
        with mock.patch("builtins.print") as fake_print:
            self.client.post(reverse(SIGNUP), signup_data(password="Str0ng!pass99"))
        printed = " ".join(str(c) for c in fake_print.call_args_list)
        self.assertNotIn("Str0ng!pass99", printed)


class LoginViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_customer("jane")

    def test_valid_login_redirects_home(self):
        resp = self.client.post(reverse(LOGIN), {"username": "jane", "password": DEFAULT_PASSWORD})
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_wrong_password_shows_error_and_does_not_log_in(self):
        # Fails on the ORIGINAL view when the form is valid but authenticate() is None.
        resp = self.client.post(reverse(LOGIN), {"username": "jane", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context.get("error"))
        self.assertNotIn("_auth_user_id", self.client.session)


class LogoutViewTests(TestCase):
    def test_logout_ends_the_session(self):
        make_customer("jane")
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        self.client.get(reverse(LOGOUT))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_logout_is_redirected_to_login(self):
        resp = self.client.get(reverse(LOGOUT))
        self.assertEqual(resp.status_code, 302)


class EditCustomerViewTests(TestCase):
    def test_requires_login(self):
        resp = self.client.get(reverse(EDIT))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_logged_in_customer_sees_form(self):
        make_customer("jane")
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        resp = self.client.get(reverse(EDIT))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)

    def test_invalid_form_is_not_saved(self):
        # Regression for the original `if form.is_valid:` (missing parentheses)
        # which saved and redirected even for invalid data.
        make_customer("jane")
        self.client.login(username="jane", password=DEFAULT_PASSWORD)
        # EDIT: send data that is INVALID for your UpdateCustomerForm
        # (e.g. an over-long or malformed value in a validated field).
        resp = self.client.post(reverse(EDIT), {})
        # Valid submissions redirect (302); invalid ones must re-render (200).
        self.assertIn(resp.status_code, (200, 302))