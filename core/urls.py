from django.urls import path, include
from . import views
urlpatterns = [
    path('', views.ClientDashboardView.as_view(), name='dashboard'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('subscription-expired/', views.subscription_expired, name='subscription_expired'),
    path('mark-notifications-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('api/get-plan-details/<int:plan_id>/', views.get_plan_details, name='get_plan_details'),
    path('api/verify-admin-password/', views.verify_admin_action_password, name='verify_admin_password'),
    path('api/lock-admin-password/', views.lock_admin_actions, name='lock_admin_password'),
]