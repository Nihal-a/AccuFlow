from django.urls import path
from . import views

urlpatterns = [
    path('', views.GodownView.as_view(), name='godown'),
    path('create/', views.AddGodownView.as_view(), name='create-godown'),
    path('delete/<int:godown_id>/', views.DeleteGodownView.as_view(), name='delete-godown'),
    path('edit/<int:godown_id>/', views.UpdateGodownView.as_view(), name='edit-godown'),  
    path('ledger/', views.GodownLedgerView.as_view(), name='godownledger'),
]