from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

from loanApp.models import (
    loanRequest,
    loanTransaction,
)
from loginApp.models import CustomerSignUp
from managerApp.forms import (
    AdminLoginForm,
    LoanCategoryForm,
)

from .constants import Endpoints, Status, Templates
from .contracts import must_return_status
from .selectors import (
    get_dashboard_statistics,
    get_objects,
)
from .services import (
    approve_loan_request,
    reject_loan_request,
    remove_customer,
)


def authenticate_superuser(request, form):
    """
    Validate administrator credentials and privileges.

    Authentication is separated from request handling
    to reduce the complexity of the login view.
    """
    if not form.is_valid():
        return None, "Invalid Username or Password "

    user = authenticate(
        request,
        username=form.cleaned_data["username"],
        password=form.cleaned_data["password"],
    )

    if user is None:
        return None, None

    if not user.is_superuser:
        return None, "You are not Super User"

    return user, None


def superuser_login_view(request):
    if request.user.is_authenticated:
        return redirect(Endpoints.HOME)

    if request.method != "POST":
        return render(request, Templates.LOGIN, {"form": AdminLoginForm(), "user": "Admin Login"})

    form = AdminLoginForm(data=request.POST)

    user, error = authenticate_superuser(request, form)

    if user is not None:
        login(request, user)
        return redirect(Endpoints.DASHBOARD)

    if error is not None:
        return render(request, Templates.LOGIN, {"form": form, "error": error})

    return render(request, Templates.LOGIN, {"form": form, "user": "Admin Login"})


@staff_member_required(login_url=Endpoints.LOGIN)
@must_return_status(200)
def dashboard(request):
    """Render the administrator dashboard."""
    return render(
        request,
        Templates.DASHBOARD,
        get_dashboard_statistics(),
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def add_category(request):
    """Handle loan category creation."""
    form = LoanCategoryForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(Endpoints.DASHBOARD)

    return render(
        request,
        Templates.CATEGORY,
        {"form": form},
    )


def list_view(template, context_key, model, related=(), **filters):
    """Build a staff-only list view (a function that returns a function)."""

    @staff_member_required(login_url=Endpoints.LOGIN)
    @must_return_status(200)
    def view(request):
        return render(
            request,
            template,
            {context_key: get_objects(model, related, **filters)},
        )

    return view


REQUEST_RELATED = ("customer", "category")

total_users = list_view(Templates.USERS, "users", CustomerSignUp, ("user",))
loan_request = list_view(
    Templates.REQUESTS, "loanrequest", loanRequest, REQUEST_RELATED, status=Status.PENDING
)
approved_loan = list_view(
    Templates.APPROVED, "approvedLoan", loanRequest, REQUEST_RELATED, status=Status.APPROVED
)
rejected_loan = list_view(
    Templates.REJECTED, "rejectedLoan", loanRequest, REQUEST_RELATED, status=Status.REJECTED
)
transaction_loan = list_view(
    Templates.TRANSACTIONS, "transactions", loanTransaction, ("customer",)
)


@staff_member_required(login_url=Endpoints.LOGIN)
@must_return_status(302)
def user_remove(request, pk):
    """Delegate customer deletion to the service layer."""
    remove_customer(pk)

    return HttpResponseRedirect(Endpoints.USERS_REDIRECT)


def render_request_list(request):
    """Render the list of pending loan requests."""
    return render(
        request,
        Templates.REQUESTS,
        {"loanrequest": get_objects(loanRequest, status=Status.PENDING)},
    )


@staff_member_required(login_url=Endpoints.LOGIN)
@must_return_status(200)
def approved_request(request, id):
    """Delegate loan approval to the service layer."""
    approve_loan_request(id)

    return render_request_list(request)


@staff_member_required(login_url=Endpoints.LOGIN)
@must_return_status(200)
def rejected_request(request, id):
    """Delegate loan rejection to the service layer."""
    reject_loan_request(id)

    return render_request_list(request)