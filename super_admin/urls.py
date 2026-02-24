from django.urls import path
from . import views

urlpatterns = [
    path('check-username-availability/', views.check_username_availability, name='check-username'),
    path('clients/', views.ClientsView.as_view(), name='clients'),
    path('clients/create/', views.ClientAddView.as_view(), name='create-client'),
    path('clients/update/<int:id>/', views.ClientUpdateView.as_view(), name='update-client'),
    path('clients/delete/<int:client_id>/', views.DeleteClientView.as_view(), name='delete-client'),
    
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscriptions'),
    path('subscriptions/create/', views.SubscriptionCreateView.as_view(), name='create-subscription'),
    path('subscriptions/update/<int:id>/', views.SubscriptionUpdateView.as_view(), name='update-subscription'),
    
    path('payments/', views.PaymentListView.as_view(), name='payments'),
    path('payments/create/', views.PaymentCreateView.as_view(), name='payment-create'),


]