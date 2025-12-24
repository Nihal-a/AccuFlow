from django.urls import path
from . import views

urlpatterns = [
    path('', views.ViewCOllectionsView.as_view(), name='viewcollections'),
] 