from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.NewCollectionView.as_view(), name='newcollection'),
]