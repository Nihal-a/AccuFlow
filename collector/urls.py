from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.CollectorView.as_view(), name='collectors'),
    path('view/<int:collector_id>/', views.CollectorDetailView.as_view(), name='view-collector'),
    path('create/', views.AddCollectorView.as_view(), name='create-collector'),
    path('delete/<int:collector_id>/', views.DeleteCollectorView.as_view(), name='delete-collector'),
    path('edit/<int:collector_id>/', views.UpdateCollectorView.as_view(), name='edit-collector'),
    
]