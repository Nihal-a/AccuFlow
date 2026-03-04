import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns,Cashs,CashBanks
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient, update_ledger
from core.authorization import get_object_for_user
from core.utils import validate_positive_decimal

class CashEntryView(View):
    def get(self,request):
        cashs = Cashs.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        cb = (
            Cashs.objects.filter(
                hold=False,
                is_active=True,
                client=getClient(request.user)
            )
            .values('cash_bank__id')
            .last()
        )

        if cb:
            cb_id = cb['cash_bank__id']
        else:
            cb_id = None
        
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
            'cb_id':cb_id
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
            seller = None 
            if types[count] == 'customers':
                supplier = None
                # Authorization: Ensure customer belongs to user's client
                customer = get_object_for_user(Customers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                seller = customer
            else:
                customer = None
                # Authorization: Ensure supplier belongs to user's client
                supplier = get_object_for_user(Suppliers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                seller = supplier
            
            # Validation
            amount_val = validate_positive_decimal(amounts[count], "Amount")

            # Management: Update Party Ledger (moving from hold=True to hold=False)
            if transactions[count] == 'Paid':
                update_ledger(where=None, to=seller, new_sale=amount_val, old_sale=0)
            else: 
                update_ledger(where=seller, to=None, new_purchase=amount_val, old_purchase=0)

            # Authorization: Ensure cash_bank belongs to user's client
            cash_bank = get_object_for_user(CashBanks, request.user, id=cashbanks_ids[count]) if cashbanks_ids[count] else None
            
            # Management: Update CashBank balance now that it's finalized (hold=False)
            if cash_bank:
                if transactions[count] == 'Received':
                    cash_bank.balance += amount_val
                else:
                    cash_bank.balance -= amount_val
                cash_bank.save()
            # Authorization: Ensure cash belongs to user's client
            cash = get_object_for_user(Cashs, request.user, id=id)
            cash.party_balance = seller.balance
            cash.cash_no = cash.cash_no
            cash.supplier = supplier
            cash.customer = customer
            cash.cash_bank = cash_bank
            cash.cash_bank_balance = cash_bank.balance if cash_bank else 0
            cash.date = dates[count]
            cash.amount = amount_val
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
        supplier_id = data.get('supplier')
        cash_bank_id = data.get('cashbank')
        date = data.get('date')
        amount = validate_positive_decimal(data.get('amount'), "Amount")
        description = data.get('description')
        type_value = data.get('type')
        cash_id = data.get('cash_id')
        transaction = data.get('transaction')
        
        customer = None
        seller = None
        supplier = None
        
        if type_value == 'customers':
            # Authorization: Ensure customer belongs to user's client
            customer = get_object_for_user(Customers, request.user, id=supplier_id) if supplier_id else None
            seller = customer
        else:
            # Authorization: Ensure supplier belongs to user's client
            supplier = get_object_for_user(Suppliers, request.user, id=supplier_id) if supplier_id else None
            seller = supplier
            
        cash = None
        if cash_id:
            # Authorization: Ensure cash belongs to user's client
            cash = get_object_for_user(Cashs, request.user, id=cash_id)
            
            cash.party_balance -= cash.amount
            
            if cash.cash_bank and not cash.hold:
                if cash.transaction == 'Received':
                    cash.cash_bank.balance -= cash.amount
                else:
                    cash.cash_bank.balance += cash.amount
                cash.cash_bank.save()

            if not cash.hold:
                if cash.transaction == 'Paid':
                    update_ledger(where=None, to=cash.party, old_sale=cash.amount)
                else:
                    update_ledger(where=cash.party, to=None, old_purchase=cash.amount)
            
            cash.cash_no = cash_no
            cash.supplier = supplier
            cash.customer = customer
            cash_bank = get_object_for_user(CashBanks, request.user, id=cash_bank_id) if cash_bank_id else None
            cash.cash_bank = cash_bank
            cash.date = date
            cash.amount = amount
            cash.description = description
            cash.transaction = transaction
            cash.client=getClient(request.user)
            
            cash.party_balance += amount
            
            if cash_bank and not cash.hold:
                if transaction == 'Received':
                    cash_bank.balance += amount
                else:
                    cash_bank.balance -= amount
                cash_bank.save()
                cash.cash_bank_balance = cash_bank.balance
            
            cash.save()
            
            if not cash.hold:
                if transaction == 'Paid':
                    update_ledger(where=None, to=seller, new_sale=amount)
                else:
                    update_ledger(where=seller, to=None, new_purchase=amount)
            
            return JsonResponse({'status':'success','message':'Cash held successfully','cash_id':cash.id,'hold':cash.hold,'cb_id':cash_bank_id}) 
        
        cash_bank = get_object_for_user(CashBanks, request.user, id=cash_bank_id) if cash_bank_id else None
        # Note: No ledger or bank update here as hold is always True for new grid entries
        cash = Cashs.objects.create(
            cash_no = cash_no,
            supplier = supplier,
            customer = customer, 
            cash_bank = cash_bank,
            date = date,
            amount = amount,
            description = description,
            transaction = transaction,
            hold = True,
            client=getClient(request.user),
            party_balance = amount,
            cash_bank_balance = cash_bank.balance if cash_bank else 0
        )
        return JsonResponse({'status':'success','message':'Cash held successfully','cash_id':cash.id,'hold':cash.hold,'cb_id':cash_bank_id})


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
    cash = get_object_for_user(Cashs, request.user, id=pk)
    
    # Reverse CashBank balance ONLY if finalized (hold=False)
    if cash.cash_bank and not cash.hold:
        if cash.transaction == 'Received':
            cash.cash_bank.balance -= cash.amount
        else:
            cash.cash_bank.balance += cash.amount
        cash.cash_bank.save()

    if not cash.hold:
        if cash.transaction == 'Paid':
            update_ledger(where=None, to=cash.party, old_sale=cash.amount, new_sale=0)
        else:
            update_ledger(where=cash.party, to=None, old_purchase=cash.amount, new_purchase=0)
            
    cash.is_active = False
    cash.save()
    return JsonResponse({'status':'success','message':'Cash deleted successfully'})
