from django.shortcuts import render,redirect, get_object_or_404
from core.models import CashBanks
from django.views import View
from django.views.generic.edit import DeleteView

from core.views import getClient
from core.authorization import get_object_for_user

class CashBankView(View):
    def get(self,request):
        cashbank = CashBanks.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'cashbank/cashbank.html',{'cashbanks':cashbank})


class AddCashBankView(View):
    def get(self,request):
        return render(request,'cashbank/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        CashBanks.objects.create(
            name=name,
            description=description,
            cashbankId = getLastCashBankNo(client=getClient(request.user)),
            client=getClient(request.user)
        )
        return redirect('cashbank')

class DeleteCashBankView(View):
    def post(self, request, cashbank_id):
        cashbank = get_object_for_user(CashBanks, request.user, id=cashbank_id)
        cashbank.is_active = False 
        cashbank.save()
        return redirect('cashbank')
 
class CashBankDetailView(View):
    def get(self, request, cashbank_id):
        cashbank = get_object_for_user(CashBanks, request.user, id=cashbank_id)
        return render(request, 'cashbank/view.html', {'cashbank': cashbank})

class UpdateCashBankView(View):
    def get(self, request, cashbank_id):
        cashbank = get_object_for_user(CashBanks, request.user, id=cashbank_id)
        return render(request, 'cashbank/update.html', {'cashbank': cashbank})

    def post(self, request, cashbank_id):
        cashbank = get_object_for_user(CashBanks, request.user, id=cashbank_id)
        cashbank.name = request.POST.get('name')
        cashbank.description = request.POST.get('description')
        if not cashbank.cashbankId:
            cashbank.cashbankId = getLastCashBankNo(getClient(request.user))
        cashbank.save()
        return redirect('cashbank')
    
    

def getLastCashBankNo(client):
    cashbanks = CashBanks.objects.filter(is_active=True, client=client).exclude(cashbankId__isnull=True).exclude(cashbankId='')
    max_num = 0
    for cb in cashbanks:
        try:
            prefix, num_str = cb.cashbankId.split('-')
            num = int(num_str)
            if num > max_num:
                max_num = num
        except ValueError:
            pass
            
    if max_num > 0:
        return f"CB-{max_num + 1}"
    return "CB-1"
     