
from django.contrib.auth import authenticate, login
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect

from managerApp.forms import (
    AdminLoginForm,
    LoanCategoryForm,
)

from loanApp.models import (
    loanRequest,
    loanTransaction,
)
from loginApp.models import CustomerSignUp

from .constants import Status, Endpoints, Templates

from .selectors import (
    get_objects,
    get_dashboard_statistics,
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
    """Handle administrator login requests."""
    if request.user.is_authenticated:
        return redirect(Endpoints.HOME)

    if request.method != "POST":
        return render(
            request,
            Templates.LOGIN,
            {
                "form": AdminLoginForm(),
                "user": "Admin Login",
            },
        )

    form = AdminLoginForm(data=request.POST)

    user, error = authenticate_superuser(
        request,
        form,
    )

    if user is not None:
        login(request, user)
        return redirect(Endpoints.DASHBOARD)

    if error is not None:
        return render(
            request,
            Templates.LOGIN,
            {
                "form": form,
                "error": error,
            },
        )

    return render(
        request,
        Templates.LOGIN,
        {
            "form": form,
            "user": "Admin Login",
        },
    )


@staff_member_required(login_url=Endpoints.LOGIN)
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


@staff_member_required(login_url=Endpoints.LOGIN)
def total_users(request):
    """Display registered customers."""
    return render(
        request,
        Templates.USERS,
        {
            "users": get_objects(CustomerSignUp),
        },
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def user_remove(request, pk):
    """
    Delegate customer deletion to the service layer.

    Original HTTP method and redirect behavior
    are preserved.
    """
    remove_customer(pk)

    return HttpResponseRedirect(
        Endpoints.USERS_REDIRECT
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def loan_request(request):
    """Display pending loan requests."""
    return render(
        request,
        Templates.REQUESTS,
        {
            "loanrequest": get_objects(
                loanRequest,
                status=Status.PENDING,
            ),
        },
    )


def render_request_list(request):
    """Render the list of pending loan requests."""
    return render(
        request,
        Templates.REQUESTS,
        {
            "loanrequest": get_objects(
                loanRequest,
                status=Status.PENDING,
            ),
        },
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def approved_request(request, id):
    """
    Delegate loan approval to the service layer.

    Existing request behavior is preserved.
    """
    approve_loan_request(id)

    return render_request_list(request)


@staff_member_required(login_url=Endpoints.LOGIN)
def rejected_request(request, id):
    """
    Delegate loan rejection to the service layer.

    Existing request behavior is preserved.
    """
    reject_loan_request(id)

    return render_request_list(request)


@staff_member_required(login_url=Endpoints.LOGIN)
def approved_loan(request):
    """Display approved loan requests."""
    return render(
        request,
        Templates.APPROVED,
        {
            "approvedLoan": get_objects(
                loanRequest,
                status=Status.APPROVED,
            ),
        },
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def rejected_loan(request):
    """Display rejected loan requests."""
    return render(
        request,
        Templates.REJECTED,
        {
            "rejectedLoan": get_objects(
                loanRequest,
                status=Status.REJECTED,
            ),
        },
    )


@staff_member_required(login_url=Endpoints.LOGIN)
def transaction_loan(request):
    """Display recorded loan transactions."""
    return render(
        request,
        Templates.TRANSACTIONS,
        {
            "transactions": get_objects(
                loanTransaction
            ),
        },
    )
