from django.urls import path
from . import views

urlpatterns = [
    path('', views.SaleEntryView.as_view(), name='sale'),
    path('create/', views.SaleAddView.as_view(), name='sale-create'),
    path('api/sale_no/', views.sale_no, name='api-sale-no'),
    path('api/sales_by_date/', views.sales_by_date, name='api-sales-by-date'),
    path('api/hold_sale/', views.SaleHold.as_view(), name='api-hold-sale'),
    path('api/delete_sale/', views.delete_sale, name='api-delete-sale'), 
] 