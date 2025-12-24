from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.PurchaseReportView.as_view(), name='purchasereport'),
]