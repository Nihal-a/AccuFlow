import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns
from django.views import View
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.db import transaction
from django.db.models import F

from core.views import getClient, update_ledger
from core.authorization import get_object_for_user
from core.utils import validate_positive_decimal
from decimal import Decimal

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
                'balance':str(customer.get_balance),
            })
        suppliersData = []
        for supplier in suppliers:
            suppliersData.append({
                'id':supplier.id,
                'name':supplier.name,
                'supplierId':supplier.supplierId,
                'balance':str(supplier.get_balance),
            })
        context = {
            'purchases':purchaseData,
            'suppliers_json':json.dumps(suppliersData),
            'customers_json':json.dumps(customersData),
            'suppliers': suppliers,
            'customers': customers,
            'godowns':godowns,
            'last_purchase_no':getLastPurchaseNo(client=getClient(request.user)),
        }
        return render(request,'purchase_entry/purchase_entry.html',context)
    
    
class PurchaseAddView(View):
    def post(self,request):
        with transaction.atomic():
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
                    customer = get_object_for_user(Customers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                    seller = customer
                else:
                    customer = None
                    supplier = get_object_for_user(Suppliers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                    seller = supplier
                godown = get_object_for_user(Godowns, request.user, id=godown_ids[count]) if godown_ids[count] else None
                purchase = get_object_for_user(Purchases, request.user, id=id)
                
                # Validation
                qty_val = Decimal(str(qtys[count] or 0))
                amount_val = Decimal(str(amounts[count] or 0))
                total_amount_val = qty_val * amount_val

                if purchase.hold:
                    godown.qty = F('qty') + qty_val  
                    godown.save()
                    update_ledger(where=seller,to=None,new_purchase=total_amount_val,new_sale=0) 
                    
                    # Refresh instances to get updated values from DB
                    seller.refresh_from_db()
                    godown.refresh_from_db()
                    
                    purchase.seller_balance = seller.balance
                    purchase.purchaser_balance = godown.get_balance

                purchase.supplier = supplier
                purchase.godown = godown
                purchase.date = dates[count]
                purchase.qty = qty_val
                purchase.amount = amount_val
                purchase.total_amount = total_amount_val    
                purchase.hold = False
                purchase.customer = customer
                purchase.client=getClient(request.user)
                
                purchase.save()  
                count += 1
        return redirect('purchase')


class PurchaseHold(View):
    def post(self,request):
        with transaction.atomic():
            data = json.loads(request.body)
            purchase_no = data.get('purchase_no')
            supplier = data.get('supplier')
            godown = data.get('godown')
            date = data.get('date')
            qty = Decimal(str(data.get('qty', 0)))
            amount = Decimal(str(data.get('amount', 0)))
            total_amount = qty * amount
            description = data.get('description')
            type_value = data.get('type')
            customer = None
            seller = None
            if type_value == 'customers':
                customer = get_object_for_user(Customers, request.user, id=supplier) if supplier else None
                supplier = None 
                seller = customer
            else:  
                customer = None
                supplier = get_object_for_user(Suppliers, request.user, id=supplier) if supplier else None
                seller = supplier
            godown = get_object_for_user(Godowns, request.user, id=godown) if godown else None
            if data.get('purchase_id'):
                purchase = get_object_for_user(Purchases, request.user, id=data.get('purchase_id'))

                old_seller = purchase.customer or purchase.supplier
                if not purchase.hold:
                    update_ledger(
                        where=purchase.party,  
                        to=None,
                        old_purchase=purchase.total_amount,
                        old_sale=0,
                        new_purchase=0,
                        new_sale=0
                    )
                    purchase.party.save()
                    purchase.godown.qty = F('qty') - purchase.qty
                    purchase.godown.save()
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
                    godown.qty = F('qty') + qty
                    godown.save()
                    
                    purchase.purchaser_balance += qty
                    purchase.seller_balance += amount
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

    if not last_purchase_no or not last_purchase_no.purchase_no:
        return 1

    if str(last_purchase_no.purchase_no).isdigit():
        return int(last_purchase_no.purchase_no) + 1

    return 1


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
    
    with transaction.atomic():
        # Authorization: Ensure purchase belongs to user's client
        purchase = get_object_for_user(Purchases, request.user, id=pk)
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
            purchase.godown.qty = F('qty') - purchase.qty
            purchase.godown.save() 
        purchase.save()
    return JsonResponse({'status':'success','message':'Purchase deleted successfully'})