from django.urls import path, include
from . import views
urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('mark-notifications-read/', views.mark_notifications_read, name='mark_notifications_read'),
]