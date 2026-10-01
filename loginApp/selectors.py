# loginApp/selectors.py
from django.shortcuts import get_object_or_404

from .models import CustomerSignUp


def get_customer(user):
    return get_object_or_404(CustomerSignUp, user=user)