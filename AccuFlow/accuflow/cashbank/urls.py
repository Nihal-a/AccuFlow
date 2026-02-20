from django.urls import path
from . import views

urlpatterns = [
    path('', views.CashBankView.as_view(), name='cashbank'),
    path('view/<int:cashbank_id>/', views.CashBankDetailView.as_view(), name='view-cashbank'),
    path('create/', views.AddCashBankView.as_view(), name='create-cashbank'),
    path('delete/<int:cashbank_id>/', views.DeleteCashBankView.as_view(), name='delete-cashbank'),
    path('edit/<int:cashbank_id>/', views.UpdateCashBankView.as_view(), name='edit-cashbank'),
    
]