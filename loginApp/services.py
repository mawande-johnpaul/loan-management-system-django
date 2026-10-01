# loginApp/services.py
from django.db import transaction

from .models import CustomerSignUp


@transaction.atomic
def register_customer(form):
    """Create the User and its CustomerSignUp profile, or neither."""
    user = form.save()
    CustomerSignUp.objects.create(user=user)
    return user