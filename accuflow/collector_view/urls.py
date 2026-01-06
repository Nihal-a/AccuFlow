from django.urls import path
from . import views

urlpatterns = [
    path('', views.CollectorCollectionsView.as_view(), name='my_collections'),
    path('detail/<int:id>/', views.CollectorCollectionDetailView.as_view(), name='my_collection_detail'),
    path('create/', views.DirectCollectionCreateView.as_view(), name='create_direct_collection'),
]
