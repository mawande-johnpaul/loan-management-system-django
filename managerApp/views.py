from datetime import date

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from loginApp.models import CustomerSignUp
from loanApp.models import CustomerLoan, loanRequest, loanTransaction
from .forms import AdminLoginForm, LoanCategoryForm


def _sum_or_zero(queryset, field):
    return queryset.aggregate(total=Sum(field))['total'] or 0


class ManagerLoanService:
    @staticmethod
    @transaction.atomic
    def approve(request_id):
        loan_obj = get_object_or_404(loanRequest, id=request_id)
        if loan_obj.status == 'approved':
            return
        payable = int(loan_obj.amount) + int(loan_obj.amount) * 0.12 * int(loan_obj.year)
        customer_loan, created = CustomerLoan.objects.get_or_create(
            customer=loan_obj.customer,
            defaults={'total_loan': loan_obj.amount, 'payable_loan': payable},
        )
        if not created:
            customer_loan.total_loan += int(loan_obj.amount)
            customer_loan.payable_loan += payable
            customer_loan.save(update_fields=['total_loan', 'payable_loan'])
        loan_obj.status = 'approved'
        loan_obj.status_date = date.today().strftime('%B %d, %Y')
        loan_obj.save(update_fields=['status', 'status_date'])

    @staticmethod
    def reject(request_id):
        loan_obj = get_object_or_404(loanRequest, id=request_id)
        if loan_obj.status != 'approved':
            loan_obj.status = 'rejected'
            loan_obj.status_date = date.today().strftime('%B %d, %Y')
            loan_obj.save(update_fields=['status', 'status_date'])


def superuser_login_view(request):
    form = AdminLoginForm(data=request.POST or None)
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        if user is not None and user.is_superuser:
            login(request, user)
            return HttpResponseRedirect(reverse('managerApp:dashboard'))
        error = 'You are not Super User' if user is not None else 'Invalid Username or Password '
        return render(request, 'admin/adminLogin.html', {'form': form, 'error': error})
    context = {'form': form, 'user': 'Admin Login'}
    if request.method == 'POST':
        context['error'] = 'Invalid Username or Password '
    return render(request, 'admin/adminLogin.html', context)


@staff_member_required(login_url='/manager/admin-login')
def dashboard(request):
    context = {
        'totalCustomer': CustomerSignUp.objects.count(),
        'request': loanRequest.objects.filter(status='pending').count(),
        'approved': loanRequest.objects.filter(status='approved').count(),
        'rejected': loanRequest.objects.filter(status='rejected').count(),
        'totalLoan': _sum_or_zero(CustomerLoan.objects.all(), 'total_loan'),
        'totalPayable': _sum_or_zero(CustomerLoan.objects.all(), 'payable_loan'),
        'totalPaid': _sum_or_zero(loanTransaction.objects.all(), 'payment'),
    }
    return render(request, 'admin/dashboard.html', context=context)


@staff_member_required(login_url='/manager/admin-login')
def add_category(request):
    form = LoanCategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('managerApp:dashboard')
    return render(request, 'admin/admin_add_category.html', {'form': form})


@staff_member_required(login_url='/manager/admin-login')
def total_users(request):
    return render(request, 'admin/customer.html', {'users': CustomerSignUp.objects.all()})


@staff_member_required(login_url='/manager/admin-login')
@require_POST
def user_remove(request, pk):
    customer = get_object_or_404(CustomerSignUp, id=pk)
    customer.user.delete()
    customer.delete()
    return HttpResponseRedirect('/manager/users')


@staff_member_required(login_url='/manager/admin-login')
def loan_request(request):
    return render(request, 'admin/request_user.html', {'loanrequest': loanRequest.objects.filter(status='pending')})


@staff_member_required(login_url='/manager/admin-login')
@require_POST
def approved_request(request, id):
    ManagerLoanService.approve(id)
    return render(request, 'admin/request_user.html', {'loanrequest': loanRequest.objects.filter(status='pending')})


@staff_member_required(login_url='/manager/admin-login')
@require_POST
def rejected_request(request, id):
    ManagerLoanService.reject(id)
    return render(request, 'admin/request_user.html', {'loanrequest': loanRequest.objects.filter(status='pending')})


@staff_member_required(login_url='/manager/admin-login')
def approved_loan(request):
    return render(request, 'admin/approved_loan.html', {'approvedLoan': loanRequest.objects.filter(status='approved')})


@staff_member_required(login_url='/manager/admin-login')
def rejected_loan(request):
    return render(request, 'admin/rejected_loan.html', {'rejectedLoan': loanRequest.objects.filter(status='rejected')})


@staff_member_required(login_url='/manager/admin-login')
def transaction_loan(request):
    return render(request, 'admin/transaction.html', {'transactions': loanTransaction.objects.all()})
