from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoanRequestForm, LoanTransactionForm
from .models import CustomerLoan, loanRequest, loanTransaction
from loginApp.models import CustomerSignUp


def _sum_or_zero(queryset, field):
    return queryset.aggregate(total=Sum(field))['total'] or 0


def _customer_for(request):
    return get_object_or_404(CustomerSignUp, user=request.user)


class CustomerDashboardService:
    @staticmethod
    def for_customer(customer):
        requests = loanRequest.objects.filter(customer=customer)
        loans = CustomerLoan.objects.filter(customer=customer)
        payments = loanTransaction.objects.filter(customer=customer)
        return {
            'request': requests.count(),
            'approved': requests.filter(status='approved').count(),
            'rejected': requests.filter(status='rejected').count(),
            'totalLoan': _sum_or_zero(loans, 'total_loan'),
            'totalPayable': _sum_or_zero(loans, 'payable_loan'),
            'totalPaid': _sum_or_zero(payments, 'payment'),
        }


def home(request):
    return render(request, 'home.html', context={})


@login_required(login_url='/account/login-customer')
def LoanRequest(request):
    form = LoanRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        loan_obj = form.save(commit=False)
        loan_obj.customer = _customer_for(request)
        loan_obj.save()
        return redirect('/')
    return render(request, 'loanApp/loanrequest.html', context={'form': form})


@login_required(login_url='/account/login-customer')
def LoanPayment(request):
    form = LoanTransactionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.customer = _customer_for(request)
        payment.save()
        return redirect('/')
    return render(request, 'loanApp/payment.html', context={'form': form})


@login_required(login_url='/account/login-customer')
def UserTransaction(request):
    transactions = loanTransaction.objects.filter(customer=_customer_for(request))
    return render(request, 'loanApp/user_transaction.html', context={'transactions': transactions})


@login_required(login_url='/account/login-customer')
def UserLoanHistory(request):
    loans = loanRequest.objects.filter(customer=_customer_for(request))
    return render(request, 'loanApp/user_loan_history.html', context={'loans': loans})


@login_required(login_url='/account/login-customer')
def UserDashboard(request):
    context = CustomerDashboardService.for_customer(_customer_for(request))
    return render(request, 'loanApp/user_dashboard.html', context=context)


def error_404_view(request, exception):
    return render(request, 'notFound.html', status=404)
