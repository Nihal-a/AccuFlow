import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accuflow.settings')
django.setup()

from django.template.loader import render_to_string
from core.models import Sales
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

try:
    from django.test import RequestFactory
    request = RequestFactory().get('/sale/sale-entry/')
    request.user = user
    from sale_entry.views import SaleEntryView
    view = SaleEntryView()
    response = view.get(request)
    print("Render successful! Length:", len(response.content))
except Exception as e:
    import traceback
    traceback.print_exc()
