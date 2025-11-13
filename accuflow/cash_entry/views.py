import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns,Cashs,CashBanks
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient

class CashEntryView(View):
    def get(self,request):
        cashs = Cashs.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        cashData = []
        for cash in cashs:
            cashData.append({
                'id':cash.id,
                'cash_no':cash.cash_no,
                'supplier':cash.supplier.name if cash.supplier else '',
                'supplier_id':cash.supplier.id if cash.supplier else '',
                'customer':cash.customer.name if cash.customer else '',
                'customer_id':cash.customer.id if cash.customer else '',
                'cashbank':cash.cash_bank.name if cash.cash_bank else '',
                'cashbank_id':cash.cash_bank.id if cash.cash_bank else '',
                'date':str(cash.date),
                'amount':cash.amount,
                'description':cash.description if cash.description else '', 
                'type':cash.which_type if cash.which_type else '',
                'transaction':cash.transaction if cash.transaction else ''
            })
        suppliers = Suppliers.objects.filter(is_active=True,client=getClient(request.user))
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        cashbanks = CashBanks.objects.filter(is_active=True,client=getClient(request.user))
        context = {
            'cashs':cashData,
            'suppliers':suppliers,
            'customers':customers,
            'last_cash_no':getLastCashNo(client=getClient(request.user)),
            'cashbanks':cashbanks,
        }
        return render(request,'cashs/cash_entry.html',context)
    
    

class CashAddView(View):
    def post(self,request):
        dates = request.POST.getlist('dates')
        amounts = request.POST.getlist('amounts')
        supplier_ids = request.POST.getlist('suppliers')
        cashbanks_ids = request.POST.getlist('cashs')
        cash_ids = request.POST.getlist('cash_ids') 
        types = request.POST.getlist('type')
        transactions = request.POST.getlist('transactions')
        count = 0
        for id in cash_ids:
            customer = None 
            if types[count] == 'customers':
                supplier = None
                customer = get_object_or_404(Customers, id=supplier_ids[count]) if supplier_ids[count] else None
            else:
                customer = None
                supplier = get_object_or_404(Suppliers, id=supplier_ids[count]) if supplier_ids[count] else None
            cash_bank = get_object_or_404(CashBanks, id=cashbanks_ids[count]) if cashbanks_ids[count] else None
            cash = get_object_or_404(Cashs, id=id)
            cash.cash_no = cash.cash_no
            cash.supplier = supplier
            cash.customer = customer
            cash.cash_bank = cash_bank
            cash.date = dates[count]
            cash.amount = amounts[count]
            cash.hold = False 
            cash.transaction = transactions[count]
            cash.client=getClient(request.user)
            cash.save()
            count += 1
        return redirect('cash')


    


class CashHold(View):
    def post(self,request):
        data = json.loads(request.body)
        cash_no = data.get('cash_no')
        supplier = data.get('supplier')
        cash_bank = data.get('cashbank')
        date = data.get('date')
        amount = data.get('amount')
        description = data.get('description')
        type_value = data.get('type')
        cash_id = data.get('cash_id')
        transaction = data.get('transaction')
        customer = None
        if type_value == 'customers':
            customer = get_object_or_404(Customers, id=supplier) if supplier else None
            supplier = None 
        else:
            customer = None
            supplier = get_object_or_404(Suppliers, id=supplier) if supplier else None
        cash = ''
        if cash_id:
            cash = get_object_or_404(Cashs, id=cash_id)
            cash.cash_no = cash_no
            cash.supplier = supplier
            cash.customer = customer
            cash.cash_bank = get_object_or_404(CashBanks, id=cash_bank) if cash_bank else None
            cash.date = date
            cash.amount = amount
            cash.description = description
            cash.transaction = transaction
            cash.client=getClient(request.user)
            cash.save()
            return JsonResponse({'status':'success','message':'Cash held successfully','cash_id':cash.id,'hold':cash.hold})
        cash = Cashs.objects.create(
            cash_no = cash_no,
            supplier = supplier,
            customer = customer, 
            cash_bank = get_object_or_404(CashBanks, id=cash_bank) if cash_bank else None,
            date = date,
            amount = amount,
            description = description,
            transaction = transaction,
            hold = True,
            client=getClient(request.user)
        )
        return JsonResponse({'status':'success','message':'Cash held successfully','cash_id':cash.id,'hold':cash.hold})
    
    
        


def getLastCashNo(client):
    last_cash_no = Cashs.objects.filter(is_active=True,client=client).order_by('-cash_no').first() 
    if last_cash_no and last_cash_no.cash_no.isdigit():
        new_cash_no = str(int(last_cash_no.cash_no) + 1).zfill(len(last_cash_no.cash_no))
    else:
        new_cash_no = '1'
    return new_cash_no
    


def Cash_no(request):
    new_cash_no = getLastCashNo(client=getClient(request.user))
    return JsonResponse({'cash_no': new_cash_no})


def cashs_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    cashs = []
    if from_date and to_date:
        cashs = Cashs.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True,
            client=getClient(request.user)
        )
        
    
    cashData = []
    total_amount = 0
    for cash in cashs:
        cashData.append({ 
            'id':cash.id,
            'cash_no':cash.cash_no,
            'supplier':cash.supplier.name if cash.supplier else '',
            'supplier_id':cash.supplier.id if cash.supplier else '',
            'customer':cash.customer.name if cash.customer else '',
            'customer_id':cash.customer.id if cash.customer else '',
            'cashbank':cash.cash_bank.name if cash.cash_bank else '',
            'cashbank_id':cash.cash_bank.id if cash.cash_bank else '',
            'cash_no':cash.cash_no,
            'date':str(cash.date),
            'amount':cash.amount,
            'description':cash.description if cash.description else '', 
            'type':cash.which_type if cash.which_type else '',
            'transaction':cash.transaction if cash.transaction else ''
        })
        total_amount += cash.amount
    return JsonResponse({'cashs': cashData, 'total_amount': total_amount})


def delete_cash(request):
    pk = request.GET.get('id') 
    cash = get_object_or_404(Cashs, id=pk)
    cash.is_active = False
    cash.save()
    return JsonResponse({'status':'success','message':'Cash deleted successfully'})
