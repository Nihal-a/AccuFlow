from django.urls import path
from . import views

urlpatterns = [
    path('', views.PayableReportView.as_view(), name='payablereport'),
]
