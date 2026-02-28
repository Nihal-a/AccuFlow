from django.urls import path
from .views import BalanceSheetView

urlpatterns = [
    path('', BalanceSheetView.as_view(), name='balance_sheet'),
]
