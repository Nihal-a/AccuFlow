from django.urls import path
from . import views

urlpatterns = [
    path('', views.NSDEntryView.as_view(), name='nsd'),
    # path('create/', views.NSDAddView.as_view(), name='nsd-create'),
]