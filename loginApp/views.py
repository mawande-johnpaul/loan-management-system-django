from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import selectors, services
from .forms import CustomerLoginForm, CustomerSignUpForm, UpdateCustomerForm


def sign_up_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))

    error = ''
    form = CustomerSignUpForm()
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            user = services.register_customer(form)
            authed = authenticate(
                request, username=user.username,
                password=form.cleaned_data['password1'])
            if authed is not None:
                login(request, authed)
                return HttpResponseRedirect(reverse('home'))
            return HttpResponseRedirect(reverse('login_App:login_customer'))
        if 'username' in form.errors:
            error = form.errors['username'][0]
        else:
            error = 'Your password is not strong enough or both passwords must match'

    return render(request, 'loginApp/signup.html',
                  {'form': form, 'user': "Customer Register", 'error': error})


def login_view(request):
    form = CustomerLoginForm()
    error = None
    if request.method == 'POST':
        form = CustomerLoginForm(data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'])
            if user is not None:
                login(request, user)
                return HttpResponseRedirect(reverse('home'))
        error = 'Invalid username or password'
    return render(request, 'loginApp/login.html',
                  {'form': form, 'user': "Customer Login", 'error': error})


@login_required()
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('home'))


@login_required(login_url='/account/login-customer')
def edit_customer(request):
    customer = selectors.get_customer(request.user)
    form = UpdateCustomerForm(instance=customer)
    if request.method == 'POST':
        form = UpdateCustomerForm(request.POST, request.FILES, instance=customer)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('home'))
    return render(request, 'loginApp/edit.html', {'form': form})