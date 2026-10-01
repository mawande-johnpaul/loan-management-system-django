"""
BASELINE (characterization) tests for the ORIGINAL loginApp code, before the SOLID refactor.

- Self-contained: no factories.py, services.py or selectors.py needed.
- Every test here should PASS on the original code.
- Classes ending in "KnownBugTests" pin CURRENT BUGGY behaviour. They are EXPECTED
  to fail after the refactor (that is the point: the failure shows the bug is fixed).

Run:  python manage.py test loginApp
"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from loginApp.models import CustomerSignUp

SIGNUP = "login_App:signup_customer"
LOGIN = "login_App:login_customer"
LOGOUT = "login_App:logout"
EDIT = "login_App:edit-customer"

PASSWORD = "pass12345"

NO_MANIFEST = override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)


def make_user(username="jane", **extra):
    return User.objects.create_user(username=username, password=PASSWORD, **extra)


def make_customer(username="jane"):
    return CustomerSignUp.objects.create(user=make_user(username))


def signup_data(username="newuser", password="Str0ng!pass99"):
    return {"username": username, "password1": password, "password2": password}


def login_as(client, username="jane"):
    assert client.login(username=username, password=PASSWORD)


# --------------------------------------------------------------------------
@NO_MANIFEST
class SignUpViewTests(TestCase):
    def test_page_loads(self):
        self.assertEqual(self.client.get(reverse(SIGNUP)).status_code, 200)

    def test_valid_signup_creates_user_and_profile_and_logs_in(self):
        resp = self.client.post(reverse(SIGNUP), signup_data())

        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        user = User.objects.get(username="newuser")
        self.assertTrue(CustomerSignUp.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_username_shows_error_and_creates_nothing(self):
        make_customer("taken")
        before = User.objects.count()

        resp = self.client.post(reverse(SIGNUP), signup_data(username="taken"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["error"], "customer already exists")
        self.assertEqual(User.objects.count(), before)

    def test_mismatched_passwords_show_error(self):
        data = signup_data()
        data["password2"] = "different"
        resp = self.client.post(reverse(SIGNUP), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("not strong enough", resp.context["error"])
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_weak_password_shows_error(self):
        resp = self.client.post(reverse(SIGNUP), signup_data(password="123"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("not strong enough", resp.context["error"])
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_logged_in_user_is_redirected_home(self):
        make_customer("jane")
        login_as(self.client)
        resp = self.client.get(reverse(SIGNUP))
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)


@NO_MANIFEST
class LoginViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_customer("jane")

    def test_page_loads(self):
        self.assertEqual(self.client.get(reverse(LOGIN)).status_code, 200)

    def test_valid_login_redirects_home(self):
        resp = self.client.post(reverse(LOGIN), {"username": "jane", "password": PASSWORD})
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_wrong_password_does_not_log_in(self):
        resp = self.client.post(reverse(LOGIN), {"username": "jane", "password": "wrong"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blank_form_shows_error(self):
        resp = self.client.post(reverse(LOGIN), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["error"], "Invalid username or password")


@NO_MANIFEST
class LogoutViewTests(TestCase):
    def test_logout_ends_the_session_and_redirects_home(self):
        make_customer("jane")
        login_as(self.client)
        resp = self.client.get(reverse(LOGOUT))
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_logout_is_sent_to_login(self):
        resp = self.client.get(reverse(LOGOUT))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])


@NO_MANIFEST
class EditCustomerViewTests(TestCase):
    def test_requires_login(self):
        resp = self.client.get(reverse(EDIT))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/login-customer", resp["Location"])

    def test_logged_in_customer_sees_form(self):
        make_customer("jane")
        login_as(self.client)
        resp = self.client.get(reverse(EDIT))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)


# --------------------------------------------------------------------------
# KNOWN BUGS: these assert the CURRENT (wrong) behaviour and should flip after the refactor.
# --------------------------------------------------------------------------
@NO_MANIFEST
class SignUpKnownBugTests(TestCase):
    def test_password_is_printed_to_stdout(self):
        with mock.patch("builtins.print") as fake_print:
            self.client.post(reverse(SIGNUP), signup_data(password="Str0ng!pass99"))
        printed = " ".join(str(c) for c in fake_print.call_args_list)
        self.assertIn("Str0ng!pass99", printed)             # refactor: assertNotIn

    def test_profile_failure_leaves_an_orphan_user(self):
        with mock.patch.object(CustomerSignUp, "save", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse(SIGNUP), signup_data())
        # The user row was created before the profile failed and nothing rolled it back.
        self.assertTrue(User.objects.filter(username="newuser").exists())   # refactor: False


@NO_MANIFEST
class EditCustomerKnownBugTests(TestCase):
    def test_invalid_post_crashes_instead_of_showing_form_errors(self):
        # `if form.is_valid:` (no parentheses) is always truthy, so form.save() runs on
        # invalid data and raises ValueError.
        # EDIT: if your UpdateCustomerForm makes every field optional, {} is valid and this
        # test needs invalid data for one of its fields instead.
        make_customer("jane")
        login_as(self.client)
        with self.assertRaises(ValueError):
            self.client.post(reverse(EDIT), {})             # refactor: 200 with form errors

    def test_user_without_profile_crashes(self):
        make_user("boss", is_staff=True)
        login_as(self.client, "boss")
        with self.assertRaises(CustomerSignUp.DoesNotExist):
            self.client.get(reverse(EDIT))                  # refactor: 404