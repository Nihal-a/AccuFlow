from django.shortcuts import render,redirect, get_object_or_404
from core.models import CashBanks
from django.views import View
from django.views.generic.edit import DeleteView

from core.views import getClient

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
    def get(self, request, cashbank_id):
        cashbank = get_object_or_404(CashBanks, id=cashbank_id)
        cashbank.is_active = False 
        cashbank.save()
        return redirect('cashbank')
 

class UpdateCashBankView(View):
    def get(self, request, cashbank_id):
        cashbank = get_object_or_404(CashBanks, id=cashbank_id)
        return render(request, 'cashbank/update.html', {'cashbank': cashbank})

    def post(self, request, cashbank_id):
        cashbank = get_object_or_404(CashBanks, id=cashbank_id)
        cashbank.name = request.POST.get('name')
        cashbank.description = request.POST.get('description')
        if not cashbank.cashbankId:
            cashbank.cashbankId = getLastCashBankNo()
        cashbank.save()
        return redirect('cashbank')
    
    

def getLastCashBankNo(client):
    last_cashbank = CashBanks.objects.filter(is_active=True,client=client).order_by('cashbankId').last()  
    if last_cashbank and last_cashbank.cashbankId != None:
        prefix, num = last_cashbank.cashbankId.split('-')
        new_cashbank_id = f"{prefix}-{int(num) + 1}"
    else: 
        
        new_cashbank_id = 'CB-1'
    return new_cashbank_id
     