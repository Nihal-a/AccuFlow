from django.urls import path
from . import views

urlpatterns = [
    path('', views.CollectionListView.as_view(), name='collection_list'),
    path('add/', views.AddCollectionView.as_view(), name='add_collection'),
    path('add/<int:id>/', views.AddCollectionView.as_view(), name='update_collection'),
    path('detail/<int:id>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    path('delete/<int:id>/', views.delete_collection, name='delete_collection'),
] 