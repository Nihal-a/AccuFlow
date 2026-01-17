from django.urls import path
from . import views

urlpatterns = [
    path('', views.CashEntryView.as_view(), name='cash'),
    path('create/', views.CashAddView.as_view(), name='cash-create'),
    path('api/cash_no/', views.Cash_no, name='api-cash-no'),
    path('api/cashs_by_date/', views.cashs_by_date, name='api-cashs-by-date'),
    path('api/hold_cash/', views.CashHold.as_view(), name='api-hold-cash'),
    path('api/delete_cash/', views.delete_cash, name='api-delete-cash'), 
] 