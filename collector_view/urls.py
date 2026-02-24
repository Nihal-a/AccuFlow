from django.urls import path
from . import views, api_views

urlpatterns = [
    path('', views.CollectorCollectionsView.as_view(), name='my_collections'),
    path('detail/<int:id>/', views.CollectorCollectionDetailView.as_view(), name='my_collection_detail'),
    path('add-items/<int:id>/', views.CollectorAddItemsView.as_view(), name='collector_add_items'),
    path('update-item/<int:id>/', api_views.CollectorUpdateItemView.as_view(), name='collector_update_item'),
]
