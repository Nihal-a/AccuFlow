from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('check-username-availability/', views.check_username_availability, name='check-username'),
    path('clients/', views.ClientsView.as_view(), name='clients'),
    path('clients/create/', views.ClientAddView.as_view(), name='create-client'),
    path('clients/update/<int:id>/', views.ClientUpdateView.as_view(), name='update-client'),
    path('clients/delete/<int:client_id>/', views.DeleteClientView.as_view(), name='delete-client'),
    path('clients/toggle-block/<int:client_id>/', views.toggle_client_block, name='toggle-client-block'),
    
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscriptions'),
    path('subscriptions/create/', views.SubscriptionCreateView.as_view(), name='create-subscription'),
    path('subscriptions/update/<int:id>/', views.SubscriptionUpdateView.as_view(), name='update-subscription'),
    
    path('payments/', views.PaymentListView.as_view(), name='payments'),
    path('payments/create/', views.PaymentCreateView.as_view(), name='payment-create'),
    path('payments/update/<int:id>/', views.PaymentUpdateView.as_view(), name='payment-update'),

    path('expenses/', views.AdminExpenseListView.as_view(), name='admin-expenses'),
    path('expenses/create/', views.AdminExpenseCreateView.as_view(), name='admin-expense-create'),
    path('expenses/update/<int:id>/', views.AdminExpenseUpdateView.as_view(), name='admin-expense-update'),
    path('expenses/delete/<int:id>/', views.AdminExpenseDeleteView.as_view(), name='admin-expense-delete'),

    path('recycle-bin/', views.AdminRecycleBinView.as_view(), name='admin_recycle_bin'),
    path('recycle-bin/<str:model_name>/', views.AdminRecycleBinListView.as_view(), name='admin_recycle_bin_list'),
    path('recycle-bin/restore/<str:model_name>/<int:pk>/', views.AdminRestoreView.as_view(), name='admin_restore_item'),
    path('recycle-bin/delete/<str:model_name>/<int:pk>/', views.AdminPermanentDeleteView.as_view(), name='admin_permanent_delete'),
]