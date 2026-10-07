from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from managerApp.forms import AdminLoginForm
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from loanApp.models import loanCategory, loanRequest, CustomerLoan, loanTransaction, LoanStatus
from .forms import LoanCategoryForm
from loginApp.models import CustomerSignUp
from django.contrib.auth.models import User
from datetime import date
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from loanApp import selectors, services

from django.db.models import Sum
# Create your views here.

def superuser_login_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))

    form = AdminLoginForm()
    error = None
    if request.method == 'POST':
        form = AdminLoginForm(data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is None:
                error = "Invalid Username or Password"
            elif not user.is_superuser:
                error = "You are not Super User"
            else:
                login(request, user)
                return HttpResponseRedirect(reverse('managerApp:dashboard'))
        else:
            error = "Invalid Username or Password"

    return render(request, 'admin/adminLogin.html',
                  {'form': form, 'user': "Admin Login", 'error': error})

# @user_passes_test(lambda u: u.is_superuser)
@staff_member_required(login_url='/manager/admin-login/')
def dashboard(request):
    stats = selectors.get_loan_stats()
    context = {
        'totalCustomer': CustomerSignUp.objects.count(),
        'request': stats['pending'],
        'approved': stats['approved'],
        'rejected': stats['rejected'],
        'totalLoan': stats['total_loan'],
        'totalPayable': stats['total_payable'],
        'totalPaid': stats['total_paid'],
    }
    return render(request, 'admin/dashboard.html', context=context)

def _pending_requests_page(request):
    pending = loanRequest.objects.filter(status=LoanStatus.PENDING)
    return render(request, 'admin/request_user.html', {'loanrequest': pending})

@staff_member_required(login_url='/manager/admin-login/')
def add_category(request):
    form = LoanCategoryForm()
    if request.method == 'POST':
        form = LoanCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('managerApp:dashboard')
    return render(request, 'admin/admin_add_category.html', {'form': form})


@staff_member_required(login_url='/manager/admin-login/')
def total_users(request):
    users = CustomerSignUp.objects.all()

    return render(request, 'admin/customer.html', context={'users': users})


@staff_member_required(login_url='/manager/admin-login/')
@require_POST
def user_remove(request, pk):
    customer = get_object_or_404(CustomerSignUp, pk=pk)
    user = customer.user          # the customer's OWN user, not User(id=pk)
    customer.delete()
    user.delete()
    return HttpResponseRedirect('/manager/users')

@staff_member_required(login_url='/manager/admin-login/')
def loan_request(request):
    loanrequest = loanRequest.objects.filter(status=LoanStatus.PENDING)
    return render(request, 'admin/request_user.html', context={'loanrequest': loanrequest})


@staff_member_required(login_url='/manager/admin-login/')
@require_POST
def approved_request(request, id):
    loan = get_object_or_404(loanRequest, id=id)
    try:
        services.approve_loan(loan)
    except ValueError:
        pass  # already approved/rejected: do nothing, never double-credit
    return _pending_requests_page(request)

@staff_member_required(login_url='/manager/admin-login/')
@require_POST
def rejected_request(request, id):
    loan = get_object_or_404(loanRequest, id=id)
    try:
        services.reject_loan(loan)
    except ValueError:
        pass
    return _pending_requests_page(request)


@staff_member_required(login_url='/manager/admin-login/')
@require_POST
def user_remove(request, pk):
    customer = get_object_or_404(CustomerSignUp, pk=pk)
    user = customer.user          # the customer's OWN user, not User(id=pk)
    customer.delete()
    user.delete()
    return HttpResponseRedirect('/manager/users')

@staff_member_required(login_url='/manager/admin-login/')
def approved_loan(request):
    # print(datetime.now())
    approvedLoan = loanRequest.objects.filter(status='approved')
    return render(request, 'admin/approved_loan.html', context={'approvedLoan': approvedLoan})


@staff_member_required(login_url='/manager/admin-login/')
def rejected_loan(request):
    rejectedLoan = loanRequest.objects.filter(status='rejected')
    return render(request, 'admin/rejected_loan.html', context={'rejectedLoan': rejectedLoan})


@staff_member_required(login_url='/manager/admin-login/')
def transaction_loan(request):
    transactions = loanTransaction.objects.all()
    return render(request, 'admin/transaction.html', context={'transactions': transactions})
