from django.urls import path
from . import views

urlpatterns = [
    path('', views.NSDEntryView.as_view(), name='nsd'),
    path('create/', views.NSDAddView.as_view(), name='nsd-create'),
    path('api/nsd_no/', views.nsd_no, name='api-nsd-no'),
    path('api/nsds_by_date/', views.nsds_by_date, name='api-nsds-by-date'),
    path('api/hold_nsd/', views.NSDHold.as_view(), name='api-hold-nsd'),
    path('api/delete_nsd/', views.delete_nsd, name='api-delete-nsd'), 
    path('api/balances/', views.nsd_balances_api, name='api-nsd-balances'),
] 