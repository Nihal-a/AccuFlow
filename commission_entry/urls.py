from django.urls import path
from . import views

urlpatterns = [
    path('', views.CommissionEntryView.as_view(), name='commission'),
    path('create/', views.CommissionAddView.as_view(), name='commission-create'),
    path('api/commission_no/', views.commission_no, name='api-commission-no'),
    path('api/commissions_by_date/', views.commissions_by_date, name='api-commissions-by-date'),
    path('api/hold_commission/', views.CommissionHold.as_view(), name='api-hold-commission'),
    path('api/delete_commission/', views.delete_commission, name='api-delete-commission'), 
] 