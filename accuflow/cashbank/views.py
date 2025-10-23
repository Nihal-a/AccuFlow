from django.shortcuts import render,redirect, get_object_or_404
from core.models import CashBanks
from django.views import View
from django.views.generic.edit import DeleteView

class CashBankView(View):
    def get(self,request):
        cashbank = CashBanks.objects.filter(is_active=True)
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
        cashbank.category = request.POST.get('name')
        cashbank.description = request.POST.get('description')
        cashbank.save()
        return redirect('cashbank')