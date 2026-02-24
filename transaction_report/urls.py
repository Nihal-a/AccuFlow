from django.urls import path
from . import views

urlpatterns = [
    path('', views.TransactionReportView.as_view(), name='transaction_report'),
]
