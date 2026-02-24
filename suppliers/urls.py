from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.SupplierView.as_view(), name='suppliers'),
    path('view/<int:supplier_id>/', views.SupplierDetailView.as_view(), name='view-supplier'),
    path('create/', views.AddSupplierView.as_view(), name='create-supplier'),
    path('delete/<int:supplier_id>/', views.DeleteSupplierView.as_view(), name='delete-supplier'),
    path('edit/<int:supplier_id>/', views.UpdateSupplierView.as_view(), name='edit-supplier'),
    
]