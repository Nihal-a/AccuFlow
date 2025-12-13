from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.CustomerLedgerView.as_view(), name='customerledger'),
]