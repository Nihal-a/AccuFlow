from django.urls import path
from . import views

urlpatterns = [
    path('', views.PurchaseEntryView.as_view(), name='purchase'),
    path('create/', views.PurchaseAddView.as_view(), name='purchase-create'),
]