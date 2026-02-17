from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProfitLossView.as_view(), name='pl_index'),
]
