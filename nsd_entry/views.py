import datetime
import json
import logging
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns,NSDs
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient, update_ledger
from core.authorization import get_object_for_user
from core.utils import validate_positive_decimal

logger = logging.getLogger(__name__)

class NSDEntryView(View):
    def get(self,request):
        nsds = NSDs.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        nsdData = []
        for nsd in nsds:
            nsdData.append({
                'id':nsd.id,
                'nsd_no':nsd.nsd_no,
                'sender_supplier':nsd.sender_supplier.name if nsd.sender_supplier else '',
                'sender_supplier_id':nsd.sender_supplier.id if nsd.sender_supplier else '',
                'sender_customer':nsd.sender_customer.name if nsd.sender_customer else '',
                'sender_customer_id':nsd.sender_customer.id if nsd.sender_customer else '',
                'receiver_supplier':nsd.receiver_supplier.name if nsd.receiver_supplier else '',
                'receiver_supplier_id':nsd.receiver_supplier.id if nsd.receiver_supplier else '',
                'receiver_customer':nsd.receiver_customer.name if nsd.receiver_customer else '',
                'receiver_customer_id':nsd.receiver_customer.id if nsd.receiver_customer else '',
                'date':str(nsd.date),
                'qty':str(nsd.qty),
                'sell_rate':str(nsd.sell_rate),
                'sell_amount':str(nsd.sell_amount),
                'purchase_rate':str(nsd.purchase_rate),
                'purchase_amount':str(nsd.purchase_amount),
                'description':nsd.description if nsd.description else '', 
                'which_receiver_type':nsd.which_receiver_type if nsd.which_receiver_type else '',
                'which_sender_type':nsd.which_sender_type if nsd.which_sender_type else '',
            })
        suppliers = Suppliers.objects.filter(is_active=True,client=getClient(request.user))
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        customersData = []
        for customer in customers:
            customersData.append({
                'id':customer.id,
                'name':customer.name,
                'customerId':customer.customerId, 
                'balance':str(customer.get_balance) if customer.get_balance else '0',
            })
        suppliersData = []
        for supplier in suppliers:
            suppliersData.append({
                'id':supplier.id,
                'name':supplier.name,
                'supplierId':supplier.supplierId,
                'balance':str(supplier.get_balance) if supplier.get_balance else '0',
            })
        context = {
            'nsds':nsdData,
            'nsds_json': json.dumps(nsdData),
            'suppliers':suppliersData,
            'suppliers_json': json.dumps(suppliersData),
            'customers':customersData,
            'customers_json': json.dumps(customersData),
            'last_nsd_no':getLastNSDNo(client=getClient(request.user)),
        }
        return render(request,'nsd_entry/nsd_entry.html',context)
    
    

class NSDAddView(View):
    def post(self,request):
        dates = request.POST.getlist('dates')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        sell_rate = request.POST.getlist('sell_rates')
        sell_amount = request.POST.getlist('sell_amounts')
        purchase_rate = request.POST.getlist('purchase_rates')
        purchase_amount = request.POST.getlist('purchase_amounts')
        supplier_ids = request.POST.getlist('suppliers')
        customer_ids = request.POST.getlist('customers')
        nsd_ids = request.POST.getlist('nsd_ids') 
        sender_types = request.POST.getlist('sender_type')
        receiver_types = request.POST.getlist('receiver_type')
        count = 0
        for id in nsd_ids:
            sender_customer = None 
            sender_customer = None
            receiver_customer = None
            receiver_supplier = None
            nsd = get_object_for_user(NSDs, request.user, id=id)
            sender = None
            receiver = None
            if receiver_types[count] == 'customers':
                receiver_customer = get_object_for_user(Customers, request.user, id=customer_ids[count]) if customer_ids[count] else None
                receiver_supplier = None
                receiver = receiver_customer
            else:
                receiver_customer = None
                receiver_supplier = get_object_for_user(Suppliers, request.user, id=customer_ids[count]) if customer_ids[count] else None     
                receiver = receiver_supplier       
            if sender_types[count] == 'customers':
                sender_customer = get_object_for_user(Customers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                sender_supplier = None 
                sender = sender_customer
            else:  
                sender_customer = None
                sender_supplier = get_object_for_user(Suppliers, request.user, id=supplier_ids[count]) if supplier_ids[count] else None
                sender = sender_supplier
            # Validation
            qty_val = validate_positive_decimal(qtys[count], "Quantity")
            sell_amount_val = validate_positive_decimal(sell_amount[count], "Sell Amount")
            purchase_amount_val = validate_positive_decimal(purchase_amount[count], "Purchase Amount")
            sell_rate_val = validate_positive_decimal(sell_rate[count], "Sell Rate")
            purchase_rate_val = validate_positive_decimal(purchase_rate[count], "Purchase Rate")

            update_ledger(where=sender,to=receiver,new_purchase=purchase_amount_val,new_sale=sell_amount_val) 
            nsd.sender_balance = sender.balance
            nsd.receiver_balance = receiver.balance
            nsd.sender_customer = sender_customer
            nsd.sender_supplier = sender_supplier
            nsd.receiver_customer = receiver_customer
            nsd.receiver_supplier = receiver_supplier
            nsd.date = dates[count]
            nsd.qty = qty_val
            nsd.sell_rate = sell_rate_val
            nsd.sell_amount = sell_amount_val
            nsd.purchase_rate = purchase_rate_val    
            nsd.purchase_amount = purchase_amount_val    
            nsd.hold = False
            nsd.client=getClient(request.user)
            nsd.save()  
            count += 1
        return redirect('nsd')



class NSDHold(View):
    def post(self,request):
        try:
            data = json.loads(request.body)
            nsd_no = data.get('nsd_no')
            supplier = data.get('supplier')
            date = data.get('date')
            qty = validate_positive_decimal(data.get('qty'), "Quantity")
            sell_rate = validate_positive_decimal(data.get('sell_rate'), "Sell Rate")
            sell_amount = validate_positive_decimal(data.get('sell_amount'), "Sell Amount")
            purchase_rate = validate_positive_decimal(data.get('purchase_rate'), "Purchase Rate")
            purchase_amount = validate_positive_decimal(data.get('purchase_amount'), "Purchase Amount")
            description = data.get('description')
            sender_type = data.get('sender_type')
            receiver_type = data.get('receiver_type')
            customer = data.get('customer') 
            sender_customer = None
            sender_supplier = None
            receiver_customer = None
            receiver_supplier = None
            sender =None
            receiver = None
            if sender_type == 'customers':
                # Authorization: Ensure customer belongs to user's client
                sender_customer = get_object_for_user(Customers, request.user, id=supplier) if supplier else None
                sender_supplier = None 
                sender = sender_customer
            else:  
                sender_customer = None
                # Authorization: Ensure supplier belongs to user's client
                sender_supplier = get_object_for_user(Suppliers, request.user, id=supplier) if supplier else None
                sender = sender_supplier
            if receiver_type == 'customers':
                # Authorization: Ensure customer belongs to user's client
                receiver_customer = get_object_for_user(Customers, request.user, id=customer) if customer else None
                receiver_supplier = None
                receiver = receiver_customer
            else:
                receiver_customer = None
                # Authorization: Ensure supplier belongs to user's client
                receiver_supplier = get_object_for_user(Suppliers, request.user, id=customer) if customer else None 
                receiver = receiver_supplier  
            if data.get('nsd_id'):
                # Authorization: Ensure nsd belongs to user's client
                nsd = get_object_for_user(NSDs, request.user, id=data.get('nsd_id'))
                if not nsd.hold:
                    update_ledger(
                        where=nsd.sender, 
                        to=nsd.receiver,
                        old_purchase=nsd.purchase_amount,
                        old_sale=nsd.sell_amount,
                        new_purchase=0,
                        new_sale=0
                    )
                    nsd.sender_balance -= nsd.sell_amount
                    nsd.receiver_balance -= nsd.purchase_amount
                nsd.nsd_no = nsd_no
                nsd.date = date
                nsd.qty = qty
                nsd.sell_rate = sell_rate
                nsd.sell_amount = sell_amount
                nsd.purchase_rate = purchase_rate
                nsd.purchase_amount = purchase_amount
                nsd.description = description
                nsd.receiver_customer = receiver_customer
                nsd.receiver_supplier = receiver_supplier
                nsd.sender_customer = sender_customer
                nsd.sender_supplier = sender_supplier
                nsd.client=getClient(request.user)
                if not nsd.hold:
                    nsd.hold = False 
                nsd.save()
                if not nsd.hold:
                    update_ledger(
                        where=sender, 
                        to=receiver,
                        new_purchase=purchase_amount,
                        new_sale=sell_amount,
                        old_purchase=0,
                        old_sale=0
                    )
                    nsd.sender_balance += sell_amount
                    nsd.receiver_balance += purchase_amount
                    nsd.save()
                return JsonResponse({'status':'success','nsd_id':nsd.id,'hold':nsd.hold})
            nsd = NSDs.objects.create(
                nsd_no=nsd_no,
                date=date,
                qty=qty,
                sell_rate=sell_rate,
                sell_amount=sell_amount,
                purchase_rate=purchase_rate,
                purchase_amount=purchase_amount,
                description=description,
                receiver_customer=receiver_customer,
                receiver_supplier=receiver_supplier,
                sender_customer=sender_customer,
                sender_supplier=sender_supplier,
                hold=True,
                client=getClient(request.user)
            )
            return JsonResponse({'status':'success','nsd_id':nsd.id,'hold':nsd.hold}) 
        
        except Exception as e:
            logger.exception("NSD hold failed")
            return JsonResponse({'status':'error','message':'An error occurred while processing the NSD.'})
        
    
    
        


def getLastNSDNo(client):
    last_nsd_no = NSDs.objects.filter(is_active=True,client=client).order_by('-nsd_no').first() 
    
    if last_nsd_no and last_nsd_no.nsd_no.isdigit():
        new_nsd_no = int(last_nsd_no.nsd_no) + 1
    else:
        new_nsd_no = 1
    return new_nsd_no


def nsd_no(request):
    new_nsd_no = getLastNSDNo(client=getClient(request.user))
    return JsonResponse({'nsd_no': new_nsd_no})


def nsds_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    nsds = []
    if from_date and to_date:
        nsds = NSDs.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True,
            client=getClient(request.user)
        )
    nsdData = []
    total_qty = 0
    total_sell_amount = 0
    total_purchase_amount = 0
    sell_rate_sum = 0
    purchase_rate_sum = 0
    count = 0
    for nsd in nsds:
        nsdData.append({ 
            'id':nsd.id,
            'nsd_no':nsd.nsd_no,
            'sender_supplier':nsd.sender_supplier.name if nsd.sender_supplier else '',
            'sender_supplier_id':nsd.sender_supplier.id if nsd.sender_supplier else '',
            'sender_customer':nsd.sender_customer.name if nsd.sender_customer else '',
            'sender_customer_id':nsd.sender_customer.id if nsd.sender_customer else '',
            'receiver_supplier':nsd.receiver_supplier.name if nsd.receiver_supplier else '',
            'receiver_supplier_id':nsd.receiver_supplier.id if nsd.receiver_supplier else '',
            'receiver_customer':nsd.receiver_customer.name if nsd.receiver_customer else '',
            'receiver_customer_id':nsd.receiver_customer.id if nsd.receiver_customer else '',
            'date':str(nsd.date),
            'qty':str(nsd.qty),
            'sell_rate':str(nsd.sell_rate),
            'sell_amount':str(nsd.sell_amount),
            'purchase_rate':str(nsd.purchase_rate),
            'purchase_amount':str(nsd.purchase_amount),
            'description':nsd.description if nsd.description else '', 
            'which_receiver_type':nsd.which_receiver_type if nsd.which_receiver_type else '',
            'which_sender_type':nsd.which_sender_type if nsd.which_sender_type else '',
        })
        total_qty += nsd.qty
        total_sell_amount += nsd.sell_amount
        sell_rate_sum += nsd.sell_rate
        total_purchase_amount += nsd.purchase_amount
        purchase_rate_sum += nsd.purchase_rate
        count += 1
    sell_rate_avg = float(sell_rate_sum / count) if count > 0 else 0
    purchase_rate_avg = float(purchase_rate_sum / count) if count > 0 else 0
    context ={
        'nsds': nsdData, 'total_qty': str(total_qty), 
        'sell_rate_avg': str(sell_rate_avg), 
        'purchase_rate_avg': str(purchase_rate_avg),
        'total_sell_amount': str(total_sell_amount),
        'total_purchase_amount': str(total_purchase_amount),
        }
    return JsonResponse(context)


def delete_nsd(request):
    pk = request.GET.get('id') 
    # Authorization: Ensure nsd belongs to user's client
    nsd = get_object_for_user(NSDs, request.user, id=pk)
    nsd.is_active = False
    if not nsd.hold:
        update_ledger(
        where=nsd.sender, 
        to=nsd.receiver,
        old_purchase=nsd.purchase_amount,
        old_sale=nsd.sell_amount,
        new_purchase=0,
        new_sale=0
    )
    nsd.save()
    return JsonResponse({'status':'success','message':'nsd deleted successfully'})