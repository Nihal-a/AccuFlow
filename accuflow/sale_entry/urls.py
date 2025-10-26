from django.urls import path
from . import views

urlpatterns = [
    path('', views.SalesEntryView.as_view(), name='sale'),
    path('create/', views.SalesAddView.as_view(), name='sale-create'),
]