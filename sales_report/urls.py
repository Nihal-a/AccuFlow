from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.SalesReportView.as_view(), name='salesreport'),
]