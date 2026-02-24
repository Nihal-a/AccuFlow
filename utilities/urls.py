from django.urls import path
from . import views

urlpatterns = [
    path('address-view/', views.AddressView.as_view(), name='address_view'),
    path('recycle-bin/', views.RecycleBinView.as_view(), name='recycle_bin'),
    path('recycle-bin/<str:model_name>/', views.RecycleBinListView.as_view(), name='recycle_bin_list'),
    path('recycle-bin/restore/<str:model_name>/<int:pk>/', views.RestoreView.as_view(), name='restore_item'),
    path('recycle-bin/delete/<str:model_name>/<int:pk>/', views.PermanentDeleteView.as_view(), name='permanent_delete'),
]
