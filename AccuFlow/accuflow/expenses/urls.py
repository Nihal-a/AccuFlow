from django.urls import path
from . import views

urlpatterns = [
    path('', views.ExpenseView.as_view(), name='expenses'),
    path('view/<int:expense_id>/', views.ExpenseDetailView.as_view(), name='view-expense'),
    path('create/', views.AddExpenseView.as_view(), name='create-expense'),
    path('delete/<int:expense_id>/', views.DeleteExpenseView.as_view(), name='delete-expense'),
    path('edit/<int:expense_id>/', views.UpdateExpenseView.as_view(), name='edit-expense'),
    
]