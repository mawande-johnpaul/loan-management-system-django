from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import get_object_or_404, render

from .forms import CustomerLoginForm, CustomerSignUpForm, UpdateCustomerForm
from .models import CustomerSignUp


def _auth_context(form, title, error=None):
    context = {'form': form, 'user': title}
    if error:
        context['error'] = error
    return context


class CustomerAccountService:
    @staticmethod
    @transaction.atomic
    def create_profile(form):
        user = form.save()
        CustomerSignUp.objects.create(user=user)
        return user


def sign_up_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))
    form = CustomerSignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = CustomerAccountService.create_profile(form)
        user = authenticate(request, username=user.username, password=form.cleaned_data['password1'])
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse('home'))
        return HttpResponseRedirect(reverse('login_App:login_customer'))

    error = None
    if request.method == 'POST' and not form.is_valid():
        username = request.POST.get('username')
        error = ('customer already exists' if username and User.objects.filter(username=username).exists()
                 else 'Your password is not strong enough or both password must be same')
    return render(request, 'loginApp/signup.html', context=_auth_context(form, 'Customer Register', error))


def login_view(request):
    form = CustomerLoginForm(data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return HttpResponseRedirect(reverse('home'))
    error = 'Invalid username or password' if request.method == 'POST' else None
    return render(request, 'loginApp/login.html', context=_auth_context(form, 'Customer Login', error))


@login_required()
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('home'))


@login_required(login_url='/account/login-customer')
def edit_customer(request):
    customer = get_object_or_404(CustomerSignUp, user=request.user)
    form = UpdateCustomerForm(request.POST or None, request.FILES or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return HttpResponseRedirect(reverse('home'))
    return render(request, 'loginApp/edit.html', context={'form': form})
