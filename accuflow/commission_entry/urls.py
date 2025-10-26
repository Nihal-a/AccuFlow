from django.urls import path
from . import views

urlpatterns = [
    path('', views.CommissionEntryView.as_view(), name='commission'),
    path('create/', views.CommissionAddView.as_view(), name='commission-create'),
]