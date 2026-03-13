from django.views.decorators.http import require_POST
import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Sales,Suppliers,Customers,Godowns
from django.views import View
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from core.views import getClient, update_ledger, calculate_customer_balance, calculate_supplier_balance
from core.authorization import get_object_for_user
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import ROUND_HALF_UP


@method_decorator(never_cache, name='dispatch')
class SaleEntryView(View):
    def get(self,request):
        client = getClient(request.user)
        sales = Sales.objects.filter(hold=True,is_active=True,client=client).select_related('supplier', 'customer', 'godown')
        saleData = []
        for sale in sales:
            saleData.append({
                'id':sale.id,
                'sale_no':sale.sale_no,
                'supplier':sale.supplier.name if sale.supplier else '',
                'supplier_id':sale.supplier.id if sale.supplier else '',
                'customer':sale.customer.name if sale.customer else '',
                'customer_id':sale.customer.id if sale.customer else '',
                'godown':sale.godown.name if sale.godown else '',
                'godown_id':sale.godown.id if sale.godown else '',
                'date':str(sale.date),
                'qty':sale.qty,
                'amount':sale.amount,
                'total_amount':sale.total_amount,
                'description':sale.description if sale.description else '', 
                'type':sale.which_type if sale.which_type else '',
            })
        suppliers = Suppliers.objects.filter(is_active=True,client=client)
        customers = Customers.objects.filter(is_active=True,client=client)
        godowns = Godowns.objects.filter(is_active=True,client=client)
        customersData = []
        for customer in customers:
            customersData.append({
                'id':customer.id,
                'name':customer.name,
                'customerId':customer.customerId, 
                'balance':str(calculate_customer_balance(customer, client)),
            })
        suppliersData = []
        for supplier in suppliers:
            suppliersData.append({
                'id':supplier.id,
                'name':supplier.name,
                'supplierId':supplier.supplierId,
                'balance':str(calculate_supplier_balance(supplier, client)),
            })
        context = {
            'sales':saleData,
            'suppliers_data':suppliersData,
            'customers_data':customersData,
            'suppliers_json':json.dumps(suppliersData),
            'customers_json':json.dumps(customersData),
            'suppliers': suppliers,
            'customers': customers,
            'godowns':godowns,
            'last_sale_no':getLastSaleNo(client=client),
        }
        return render(request,'sale_entry/sale_entry.html',context)
    
    

@method_decorator(never_cache, name='dispatch')
class SaleAddView(View):
    @transaction.atomic
    def post(self,request):
        dates = request.POST.getlist('dates')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        supplier_ids = request.POST.getlist('suppliers')
        customer_ids = request.POST.getlist('customers')
        godown_ids = request.POST.getlist('godowns')
        sale_ids = request.POST.getlist('sale_ids') 
        types = request.POST.getlist('type')
        
        # Validating Array Lengths to prevent index errors and data corruption
        expected_len = len(sale_ids)
        if not all(len(lst) == expected_len for lst in [dates, qtys, amounts, customer_ids, godown_ids, types]):
            # While redirect is the standard here, you could also return a 400 error.
            # Using redirect to maintain consistent behavior, but skipping the loop.
            return redirect('sale')
            
        count = 0
        
        # Step 1: Pre-aggregate godown deductions to avoid circular deadlocks
        godown_deductions = {}
        for id in sale_ids:
            godown_id = godown_ids[count]
            if godown_id:
                try:
                    qty_val = Decimal(str(qtys[count] or 0))
                except Exception:
                    qty_val = Decimal('0.00')
                
                if godown_id not in godown_deductions:
                    godown_deductions[godown_id] = Decimal('0.00')
                godown_deductions[godown_id] += qty_val
            count += 1
            
        # Step 2: Lock godowns in primary key order to prevent deadlocks
        sorted_godown_ids = sorted([g for g in godown_deductions.keys()])
        godown_objects = {}
        for gid in sorted_godown_ids:
            godown = get_object_for_user(Godowns, request.user, id=gid)
            godown_locked = Godowns.objects.select_for_update().get(pk=godown.pk)
            # Apply aggregated deduction
            godown_locked.qty = Decimal(str(godown_locked.qty)) - godown_deductions[gid]
            godown_locked.save()
            godown_objects[gid] = godown_locked
            
        # Step 3: Process the sale records and ledgers
        count = 0
        for id in sale_ids:
            customer = None 
            seller = None
            if types[count] == 'customers':
                supplier = None
                # Authorization: Ensure customer belongs to user's client
                customer = get_object_for_user(Customers, request.user, id=customer_ids[count]) if customer_ids[count] else None
                seller = customer
            else:
                customer = None
                # Authorization: Ensure supplier belongs to user's client
                supplier = get_object_for_user(Suppliers, request.user, id=customer_ids[count]) if customer_ids[count] else None
                seller = supplier
            
            godown = godown_objects.get(godown_ids[count]) if godown_ids[count] else None
            sale = get_object_for_user(Sales, request.user, id=id)
            
            try:
                qty_val = Decimal(str(qtys[count] or 0))
                amount_val = Decimal(str(amounts[count] or 0))
                total_amount_val = (qty_val * amount_val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                # Catch InvalidOperation from decimal parsing
                return redirect('sale')

            update_ledger(where=None,to=seller,new_purchase=total_amount_val,new_sale=total_amount_val) 
            sale.seller_balance = seller.balance if seller else Decimal('0.00')
            sale.purchaser_balance = godown.get_balance if godown else Decimal('0.00')
            sale.supplier = supplier
            sale.godown = godown
            sale.date = dates[count]
            sale.qty = qty_val
            sale.amount = amount_val
            sale.total_amount = total_amount_val    
            sale.hold = False
            sale.customer = customer
            sale.client=getClient(request.user)
            sale.save()  
            count += 1
        return redirect('sale')


    


@method_decorator(never_cache, name='dispatch')
class SaleHold(View):
    @transaction.atomic
    def post(self,request):
        data = json.loads(request.body)
        sale_no = data.get('sale_no')
        supplier = data.get('customer')
        godown = data.get('godown')
        date = data.get('date')
        try:
            qty = Decimal(str(data.get('qty', 0)))
            amount = Decimal(str(data.get('amount', 0)))
            total_amount = (qty * amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid numeric data for qty or amount.'}, status=400)

        description = data.get('description')
        type_value = data.get('type')
        customer = None
        seller = None
        if type_value == 'customers':
            # Authorization: Ensure customer belongs to user's client
            customer = get_object_for_user(Customers, request.user, id=supplier) if supplier else None
            supplier = None 
            seller = customer
        else:  
            customer = None
            # Authorization: Ensure supplier belongs to user's client
            supplier = get_object_for_user(Suppliers, request.user, id=supplier) if supplier else None
            seller = supplier
        # Authorization: Ensure godown belongs to user's client
        godown = get_object_for_user(Godowns, request.user, id=godown) if godown else None
        if data.get('sale_id'):
            # Authorization: Ensure sale belongs to user's client
            sale = get_object_for_user(Sales, request.user, id=data.get('sale_id'))
            if not sale.hold:
                update_ledger(
                    where=None,  
                    to=sale.party,
                    old_purchase=sale.total_amount,
                    old_sale=sale.total_amount,
                    new_purchase=0,
                    new_sale=0
                )
                godown = Godowns.objects.select_for_update().get(pk=godown.pk)
                godown.qty += sale.qty
                godown.save()
                sale.purchaser_balance = sale.purchaser_balance - sale.qty
                sale.seller_balance = sale.seller_balance - sale.amount
            sale.sale_no = sale_no
            sale.supplier = supplier
            sale.godown = godown
            sale.date = date
            sale.qty = qty
            sale.amount = amount
            sale.total_amount = total_amount
            sale.description = description
            sale.type = type_value
            sale.customer = customer
            sale.client=getClient(request.user)
            if not sale.hold:
                sale.hold = False 
            sale.save()
            if not sale.hold:
                update_ledger(
                    to=seller, 
                    where=None,
                    old_purchase=0, 
                    old_sale=0,
                    new_purchase=total_amount,
                    new_sale=total_amount,
                )
                godown = Godowns.objects.select_for_update().get(pk=godown.pk)
                godown.qty -= sale.qty
                godown.save()
                sale.purchaser_balance = Decimal(str(sale.purchaser_balance)) + qty
                sale.seller_balance = Decimal(str(sale.seller_balance)) + amount
                sale.save()
            return JsonResponse({'status':'success','sale_id':sale.id,'hold':sale.hold})
        sale = Sales.objects.create(
            sale_no=sale_no,
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
        return JsonResponse({'status':'success','sale_id':sale.id,'hold':sale.hold}) 
    
    
        


def getLastSaleNo(client):
    last_sale_no = Sales.objects.filter(is_active=True,client=client).order_by('-sale_no').first() 
    
    if last_sale_no and last_sale_no.sale_no.isdigit():
        new_sale_no = int(last_sale_no.sale_no) + 1
    else:
        new_sale_no = 1
    return new_sale_no


@login_required
@never_cache
def sale_no(request):
    new_sale_no = getLastSaleNo(client=getClient(request.user))
    return JsonResponse({'sale_no': new_sale_no})


@login_required
@never_cache
def sales_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    sales = []
    if from_date and to_date:
        sales = Sales.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True,
            client=getClient(request.user)
        ).select_related('supplier', 'customer', 'godown')
    saleData = []
    total_qty = Decimal('0.0000')
    total_amount = Decimal('0.0000')
    rate_sum = Decimal('0.0000')
    count = 0
    for sale in sales:
        saleData.append({ 
            'id':sale.id,
            'sale_no':sale.sale_no,
            'supplier':sale.supplier.name if sale.supplier else '',
            'supplier_id':sale.supplier.id if sale.supplier else '',
            'godown':sale.godown.name if sale.godown else '',
            'godown_id':sale.godown.id if sale.godown else '',
            'customer':sale.customer.name if sale.customer else '',
            'customer_id':sale.customer.id if sale.customer else '',
            'date':str(sale.date),
            'qty':sale.qty,
            'amount':sale.amount,
            'total_amount':sale.total_amount,
            'description':sale.description if sale.description else '', 
            'type':sale.which_type if sale.which_type else '',
        })
        total_qty += sale.qty
        total_amount += sale.total_amount
        rate_sum += sale.amount
        count += 1
    rate_avg = rate_sum / count if count > 0 else 0
    return JsonResponse({'sales': saleData, 'total_qty': total_qty, 'total_amount': total_amount, 'rate_avg': rate_avg})


@never_cache
@require_POST
@transaction.atomic
def delete_sale(request):
    try:
        data = json.loads(request.body)
        pk = data.get('id')
    except json.JSONDecodeError:
        pk = request.POST.get('id')
        
    if not pk:
        return JsonResponse({'status': 'error', 'message': 'No ID provided'}, status=400)
        
    sale = get_object_for_user(Sales, request.user, id=pk)
    sale.is_active = False
    if not sale.hold:
        update_ledger(
            to=sale.party,  
            where=None,
            old_purchase=sale.total_amount,
            old_sale=sale.total_amount,
            new_purchase=0,
            new_sale=0
        )
        # Lock godown row to prevent concurrent qty race conditions
        godown_locked = Godowns.objects.select_for_update().get(pk=sale.godown.pk)
        godown_locked.qty += sale.qty
        godown_locked.save()
    sale.save()
    return JsonResponse({'status':'success','message':'sale deleted successfully'})


@login_required
@never_cache
def sale_balances_api(request):
    client = getClient(request.user)
    suppliers = Suppliers.objects.filter(is_active=True, client=client)
    customers = Customers.objects.filter(is_active=True, client=client)
    godowns = Godowns.objects.filter(is_active=True, client=client)
    data = {
        'suppliers': {str(s.id): str(calculate_supplier_balance(s, client)) for s in suppliers},
        'customers': {str(c.id): str(calculate_customer_balance(c, client)) for c in customers},
        'godowns': {str(g.id): str(g.qty) for g in godowns},
    }
    return JsonResponse(data)