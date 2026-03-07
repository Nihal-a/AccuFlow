from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.ExpenseLedgerView.as_view(), name='expenseledger'),
]
