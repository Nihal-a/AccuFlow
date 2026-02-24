from django.urls import path
from . import views

urlpatterns = [
    path('', views.CollectionReportView.as_view(), name='collectionreport'),
]
