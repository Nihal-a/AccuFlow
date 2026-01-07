from django.urls import path
from . import views

urlpatterns = [
    path('', views.StockTransferView.as_view(), name='stocktransfer'),
    path('add/', views.StockTransferAddView.as_view(), name='stocktransfer_add'),
    path('api/transfer-no/', views.get_transfer_no_api, name='api-transfer-no'),
]