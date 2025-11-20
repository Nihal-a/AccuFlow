from django.shortcuts import render,redirect, get_object_or_404
from core.models import CashBanks
from django.views import View
from core.views import getClient

class CashBankView(View):
    def get(self,request):
        cashbank_balances = CashBanks.objects.all()
        return render(request,'cashbank_balance/cashbank_balance.html',{'cashbank_balances':cashbank_balances})

