from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.StockView.as_view(), name='stockview'),
]