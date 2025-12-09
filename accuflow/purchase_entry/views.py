import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns
from django.views import View
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.db.models import Q

from core.views import getClient, update_ledger

class PurchaseEntryView(View):
    def get(self,request):
        purchases = Purchases.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        purchaseData = []
        for purchase in purchases:
            purchaseData.append({
                'id':purchase.id,
                'purchase_no':purchase.purchase_no,
                'supplier':purchase.supplier.name if purchase.supplier else '',
                'supplier_id':purchase.supplier.id if purchase.supplier else '',
                'customer':purchase.customer.name if purchase.customer else '',
                'customer_id':purchase.customer.id if purchase.customer else '',
                'godown':purchase.godown.name if purchase.godown else '',
                'godown_id':purchase.godown.id if purchase.godown else '',
                'date':str(purchase.date),
                'qty':purchase.qty,
                'amount':purchase.amount,
                'total_amount':purchase.total_amount,
                'description':purchase.description if purchase.description else '', 
                'type':purchase.which_type if purchase.which_type else '',
            })
        suppliers = Suppliers.objects.filter(is_active=True,client=getClient(request.user))
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        godowns = Godowns.objects.filter(is_active=True,client=getClient(request.user))
        customersData = []
        for customer in customers:
            customersData.append({
                'id':customer.id,
                'name':customer.name,
                'customerId':customer.customerId, 
                'balance':customer.balance,
            })
        suppliersData = []
        for supplier in suppliers:
            suppliersData.append({
                'id':supplier.id,
                'name':supplier.name,
                'supplierId':supplier.supplierId,
                'balance':supplier.balance,
            })
        context = {
            'purchases':purchaseData,
            'suppliers':suppliersData,
            'customers':customersData,
            'godowns':godowns,
            'last_purchase_no':getLastPurchaseNo(client=getClient(request.user)),
        }
        return render(request,'purchase_entry/purchase_entry.html',context)
    
    

class PurchaseAddView(View):
    def post(self,request):
        dates = request.POST.getlist('dates')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        supplier_ids = request.POST.getlist('suppliers')
        customer_ids = request.POST.getlist('customers')
        godown_ids = request.POST.getlist('godowns')
        purchase_ids = request.POST.getlist('purchase_ids') 
        types = request.POST.getlist('type')
        count = 0
        seller = None
        for id in purchase_ids:
            customer = None 
            if types[count] == 'customers':
                supplier = None
                customer = get_object_or_404(Customers, id=supplier_ids[count]) if supplier_ids[count] else None
                seller = customer
            else:
                customer = None
                supplier = get_object_or_404(Suppliers, id=supplier_ids[count]) if supplier_ids[count] else None
                seller = supplier
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            purchase = Purchases.objects.get(id=id)
            godown.qty += float(qtys[count])  
            godown.save()
            # update_ledger(where=purchase.party,to=None,old_purchase=purchase.total_amount,old_sale=purchase.total_amount)
            update_ledger(where=seller,to=None,new_purchase=total_amounts[count],new_sale=0) 
            purchase.seller_balance = seller.balance
            purchase.purchaser_balance = godown.get_balance
            purchase.supplier = supplier
            purchase.godown = godown
            purchase.date = dates[count]
            purchase.qty = qtys[count]
            purchase.amount = amounts[count]
            purchase.total_amount = total_amounts[count]    
            purchase.hold = False
            purchase.customer = customer
            purchase.client=getClient(request.user)
            
            purchase.save()  
            count += 1
        return redirect('purchase')


    


class PurchaseHold(View):
    def post(self,request):
        data = json.loads(request.body)
        purchase_no = data.get('purchase_no')
        supplier = data.get('supplier')
        godown = data.get('godown')
        date = data.get('date')
        qty = data.get('qty')
        amount = data.get('amount')
        total_amount = data.get('total_amount')
        description = data.get('description')
        type_value = data.get('type')
        customer = None
        seller = None
        if type_value == 'customers':
            customer = get_object_or_404(Customers, id=supplier) if supplier else None
            supplier = None 
            seller = customer
        else:  
            customer = None
            
            supplier = get_object_or_404(Suppliers, id=supplier) if supplier else None
            seller = supplier
        godown = get_object_or_404(Godowns, id=godown) if godown else None
        if data.get('purchase_id'):
            purchase = get_object_or_404(Purchases, id=data.get('purchase_id'))

            old_seller = purchase.customer or purchase.supplier
            if not purchase.hold:
                print('updating ledger for old seller')
                update_ledger(
                    where=purchase.party,  
                    to=None,
                    old_purchase=purchase.total_amount,
                    old_sale=0,
                    new_purchase=0,
                    new_sale=0
                )
                purchase.party.save()
                godown.qty -= purchase.qty
                godown.save()
                purchase.purchaser_balance = purchase.purchaser_balance - purchase.qty
                purchase.seller_balance = purchase.seller_balance - purchase.amount
            purchase.purchase_no = purchase_no 
            purchase.supplier = supplier
            purchase.customer = customer
            purchase.godown = godown
            purchase.date = date
            purchase.qty = qty
            purchase.amount = amount
            purchase.total_amount = total_amount
            purchase.description = description
            purchase.type = type_value
            purchase.client = getClient(request.user)
            purchase.save()
            new_seller = customer or supplier
            if not purchase.hold:
                update_ledger(
                    where=new_seller, 
                    to=None,
                    old_purchase=0, 
                    old_sale=0,
                    new_purchase=total_amount,
                    new_sale=0,
                )
                godown.qty += float(qty)
                godown.save()
                purchase.purchaser_balance += float(qty)
                purchase.seller_balance += float(amount)
                purchase.save()
                

            return JsonResponse({'status':'success','purchase_id':purchase.id,'hold':purchase.hold})
        purchase = Purchases.objects.create(
            purchase_no=purchase_no,
            supplier=supplier,
            godown=godown,
            date=date,
            qty=qty,
            amount=amount,
            total_amount=total_amount,
            description=description,
            type=type_value,
            customer=customer,
            hold=True,
            client=getClient(request.user)
        )
        return JsonResponse({'status':'success','purchase_id':purchase.id,'hold':purchase.hold}) 
    
    
        


def getLastPurchaseNo(client):
    last_purchase_no = Purchases.objects.filter(is_active=True,client=client).order_by('-purchase_no').first() 
    if last_purchase_no and last_purchase_no.purchase_no and last_purchase_no.purchase_no.isdigit():
        new_purchase_no = int(last_purchase_no.purchase_no) + 1   
    else:
        new_purchase_no = 1
    return new_purchase_no


def purchase_no(request):
    new_purchase_no = getLastPurchaseNo(client=getClient(request.user))
    return JsonResponse({'purchase_no': new_purchase_no})


def purchases_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    purchases = []
    if from_date and to_date:
        purchases = Purchases.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True,
            client=getClient(request.user)
        )
    purchaseData = []
    total_qty = 0
    total_amount = 0
    rate_sum = 0
    count = 0
    for purchase in purchases:
        purchaseData.append({ 
            'id':purchase.id,
            'purchase_no':purchase.purchase_no,
            'supplier':purchase.supplier.name if purchase.supplier else '',
            'supplier_id':purchase.supplier.id if purchase.supplier else '',
            'godown':purchase.godown.name if purchase.godown else '',
            'godown_id':purchase.godown.id if purchase.godown else '',
            'customer':purchase.customer.name if purchase.customer else '',
            'customer_id':purchase.customer.id if purchase.customer else '',
            'date':str(purchase.date),
            'qty':purchase.qty,
            'amount':purchase.amount,
            'total_amount':purchase.total_amount,
            'description':purchase.description if purchase.description else '', 
            'type':purchase.which_type if purchase.which_type else '',
        })
        total_qty += purchase.qty
        total_amount += purchase.total_amount
        rate_sum += purchase.amount
        count += 1
    rate_avg = rate_sum / count if count > 0 else 0
    return JsonResponse({'purchases': purchaseData, 'total_qty': total_qty, 'total_amount': total_amount, 'rate_avg': rate_avg})


def delete_purchase(request):
    pk = request.GET.get('id') 
    purchase = get_object_or_404(Purchases, id=pk)
    purchase.is_active = False
    if not purchase.hold:
        update_ledger(
        where=purchase.party, 
        to=None,
        old_purchase=purchase.total_amount,
        old_sale=purchase.total_amount,
        new_purchase=0,
        new_sale=0
    )
        purchase.godown.qty -= purchase.qty
        purchase.godown.save() 
    purchase.save()
    return JsonResponse({'status':'success','message':'Purchase deleted successfully'})