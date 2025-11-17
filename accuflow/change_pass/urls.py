from django.urls import path
from .views import ChangePassView

urlpatterns = [
    path('', ChangePassView.as_view(), name='changepass'),
]
