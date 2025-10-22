from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.CustomerView.as_view(), name='customers'),
    path('create/', views.AddCustomerView.as_view(), name='create-customer'),
    path('delete/<int:customer_id>/', views.DeleteCustomerView.as_view(), name='delete-customer'),
    path('edit/<int:customer_id>/', views.UpdateCustomerView.as_view(), name='edit-customer'),
    
]