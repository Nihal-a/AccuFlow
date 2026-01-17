from django.urls import path
from . import views

urlpatterns = [
    path('customer/', views.OutstandingCustomerView.as_view(), name='outstanding_customer'),
    path('supplier/', views.OutstandingSupplierView.as_view(), name='outstanding_supplier'),
]
