from django.shortcuts import render,redirect, get_object_or_404
from core.models import Godowns
from django.views import View
from core.views import getClient

from core.views import getClient

class GodownView(View):
    def get(self,request):
        godown = Godowns.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'godown/godown.html',{'godowns':godown})


class AddGodownView(View):
    def get(self,request):
        return render(request,'godown/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        open_credit = request.POST.get('open_credit',0)
        open_debit = request.POST.get('open_debit',0)
        otc_credit = request.POST.get('otc_credit',0)
        otc_debit = request.POST.get('otc_debit',0)
        open_balance = float(open_debit)-float(open_credit)
        otc_balance = float(otc_debit) - float(otc_credit)
        balance = otc_balance + open_balance
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        
        credit = 0
        debit = 0
        if balance> 0:
            debit = balance
            credit = 0 
        elif balance< 0:
            credit = -balance 
            debit = 0
        godown = Godowns.objects.create(
            name=name,
            phone=phone,
            address=address,
            open_credit=open_credit,
            open_debit=open_debit,
            otc_credit=otc_credit,
            otc_debit=otc_debit,
            godownId=new_godown_id(client=getClient(request.user)),
            client=getClient(request.user),
            open_balance = open_balance,
            otc_balance = otc_balance,
            balance = balance,
            credit = credit,
            debit = debit
        )
        if wa:
            godown.country_code = country_code
            godown.wa = wa
            godown.save()
        return redirect('godown')

class DeleteGodownView(View):
    def get(self, request, godown_id):
        godown = get_object_or_404(Godowns, id=godown_id)
        godown.is_active = False 
        godown.save()
        return redirect('godown')
 

class UpdateGodownView(View):
    def get(self, request, godown_id): 
        godown = get_object_or_404(Godowns, id=godown_id)
        return render(request, 'godown/update.html', {'godown': godown})

    def post(self, request, godown_id):
        godown = get_object_or_404(Godowns, id=godown_id)
        godown.name = request.POST.get('name')
        godown.phone = request.POST.get('phone')
        godown.address = request.POST.get('address')
        godown.open_credit = request.POST.get('open_credit', 0)
        godown.open_debit = request.POST.get('open_debit', 0)
        godown.otc_credit = request.POST.get('otc_credit', 0)
        godown.otc_debit = request.POST.get('otc_debit', 0)
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        godown.client = getClient(request.user)
        godown.balance -= (godown.otc_balance + godown.open_balance)
        godown.credit -= godown.credit
        godown.debit -= godown.debit
        open_balance = float(request.POST.get('open_debit', 0))-float(request.POST.get('open_credit', 0))
        otc_balance = float(request.POST.get('otc_debit', 0))-float(request.POST.get('otc_credit', 0))
        godown.open_balance = open_balance
        godown.otc_balance = otc_balance
        godown.balance += (otc_balance + open_balance)
        if (otc_balance + open_balance)> 0:
            godown.debit = (otc_balance + open_balance)
            godown.credit = 0
        elif (otc_balance + open_balance)< 0:
            godown.credit = -(otc_balance + open_balance)
            godown.debit = 0
        if wa:
            godown.country_code = country_code
            godown.wa = wa
        if godown.godownId is None:
            godown.godownId = new_godown_id(client=getClient(request.user)) 
        godown.save()
        return redirect('godown')
    
    
def new_godown_id(client):
    last_godown = Godowns.objects.filter(is_active=True,client=client).order_by('godownId').last() 
    if last_godown and last_godown.godownId != None:
        prefix, num = last_godown.godownId.split('-')
        new_godown_id = f"{prefix}-{int(num) + 1}"
    else: 
        new_godown_id = 'G-1'
    return str(new_godown_id)