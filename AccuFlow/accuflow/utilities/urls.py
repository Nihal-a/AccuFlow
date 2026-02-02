from django.urls import path
from . import views

urlpatterns = [
    path('address-view/', views.AddressView.as_view(), name='address_view'),
]
