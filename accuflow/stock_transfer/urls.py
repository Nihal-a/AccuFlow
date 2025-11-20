from django.urls import path
from . import views

urlpatterns = [
    path('', views.StockTransferView.as_view(), name='stocktransfer'),
] 