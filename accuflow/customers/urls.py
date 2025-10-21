from django.urls import path, include
from . import views

urlpatterns = [
    path('add/', views.add, name='add_customer'),
    path('', views.test, name='customer'),
]