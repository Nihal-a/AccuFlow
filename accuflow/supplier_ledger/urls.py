from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.SupplierLedgerView.as_view(), name='supplierledger'),
]