from django.urls import path
from .views import TrialBalanceView

urlpatterns = [
    path('', TrialBalanceView.as_view(), name='trial_balance'),
]
