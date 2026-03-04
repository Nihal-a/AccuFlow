from django.urls import path
from . import views

urlpatterns = [
    path('', views.PurchaseEntryView.as_view(), name='purchase'),
    path('create/', views.PurchaseAddView.as_view(), name='purchase-create'),
    path('api/purchase_no/', views.purchase_no, name='api-purchase-no'),
    path('api/purchases_by_date/', views.purchases_by_date, name='api-purchases-by-date'),
    path('api/hold_purchase/', views.PurchaseHold.as_view(), name='api-hold-purchase'),
    path('api/delete_purchase/', views.delete_purchase, name='api-delete-purchase'), 
    path('api/balances/', views.purchase_balances_api, name='api-purchase-balances'),
] 