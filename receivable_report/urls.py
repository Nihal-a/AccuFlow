from django.urls import path
from . import views

urlpatterns = [
    path('', views.ReceivableReportView.as_view(), name='receivablereport'),
]
