from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.PendingApprovalView.as_view(), name='pendingapproval'),
    path('detail/<int:id>/', views.PendingApprovalDetailView.as_view(), name='pending_approval_detail'),
]