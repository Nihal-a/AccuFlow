from django.urls import path
from . import views

urlpatterns = [
    path('', views.StockTransferView.as_view(), name='stocktransfer'),
    path('add/', views.StockTransferAddView.as_view(), name='stocktransfer_add'),
    path('api/transfer-no/', views.get_transfer_no_api, name='api-transfer-no'),
    path('api/hold_transfer/', views.StockTransferHoldView.as_view(), name='api-hold-transfer'),
    path('api/delete_transfer/', views.delete_transfer_api, name='api-delete-transfer'),
]