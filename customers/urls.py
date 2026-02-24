from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.CustomerView.as_view(), name='customers'),
    path('view/<int:customer_id>/', views.CustomerDetailView.as_view(), name='view-customer'),
    path('create/', views.AddCustomerView.as_view(), name='create-customer'),
    path('delete/<int:customer_id>/', views.DeleteCustomerView.as_view(), name='delete-customer'),
    path('edit/<int:customer_id>/', views.UpdateCustomerView.as_view(), name='edit-customer'),
    path('ledger/', views.CustomerLedgerView.as_view(), name='customerledger'),
]