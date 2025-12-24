from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.GodownLedgerView.as_view(), name='pendingapproval'),
]