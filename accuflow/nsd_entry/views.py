import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns,NSDs
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

class NSDEntryView(View):
    def get(self,request):
        nsds = NSDs.objects.filter(hold=True,is_active=True)
        nsdData = []
        for nsd in nsds:
            nsdData.append({
                'id':nsd.id,
                'nsd_no':nsd.nsd_no,
                'supplier':nsd.supplier.name if nsd.supplier else '',
                'supplier_id':nsd.supplier.id if nsd.supplier else '',
                'customer':nsd.customer.name if nsd.customer else '',
                'customer_id':nsd.customer.id if nsd.customer else '',
                'date':str(nsd.date),
                'qty':nsd.qty,
                'sell_rate':nsd.sell_rate,
                'sell_amount':nsd.sell_amount,
                'purchase_rate':nsd.purchase_rate,
                'purchase_amount':nsd.purchase_amount,
                'description':nsd.description if nsd.description else '', 
                'type':nsd.which_type if nsd.which_type else '',
            })
        suppliers = Suppliers.objects.filter(is_active=True)
        customers = Customers.objects.filter(is_active=True)
        customersData = []
        for customer in customers:
            customersData.append({
                'id':customer.id,
                'name':customer.name,
                'customerId':customer.customerId, 
                'balance':customer.get_balance,
            })
        suppliersData = []
        for supplier in suppliers:
            suppliersData.append({
                'id':supplier.id,
                'name':supplier.name,
                'supplierId':supplier.supplierId,
                'balance':supplier.get_balance,
            })
        context = {
            'nsds':nsdData,
            'suppliers':suppliersData,
            'customers':customersData,
            'last_nsd_no':getLastNSDNo(),
        }
        return render(request,'nsd_entry/nsd_entry.html',context)
    
    

class NSDAddView(View):
    def post(self,request):
        dates = request.POST.getlist('dates')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        sell_rate = request.POST.getlist('sell_rate')
        sell_amount = request.POST.getlist('sell_amount')
        purchase_rate = request.POST.getlist('purchase_rate')
        purchase_amount = request.POST.getlist('purchase_amount')
        supplier_ids = request.POST.getlist('suppliers')
        customer_ids = request.POST.getlist('customers')
        nsd_ids = request.POST.getlist('nsd_ids') 
        types = request.POST.getlist('type')
        count = 0
        for id in nsd_ids:
            customer = None 
            if types[count] == 'customers':
                supplier = None
                customer = get_object_or_404(Customers, id=supplier_ids[count]) if supplier_ids[count] else None
            else:
                customer = None
                supplier = get_object_or_404(Suppliers, id=supplier_ids[count]) if supplier_ids[count] else None
            nsd = NSDs.objects.get(id=id)
            nsd.supplier = supplier
            nsd.date = dates[count]
            nsd.qty = qtys[count]
            nsd.sell_rate = sell_rate[count]
            nsd.sell_amount = sell_amount[count]
            nsd.purchase_rate = purchase_rate[count]    
            nsd.purchase_amount = purchase_amount[count]    
            nsd.hold = False
            nsd.customer = customer
            nsd.save()  
            count += 1
        return redirect('nsd')



class NSDHold(View):
    def post(self,request):
        data = json.loads(request.body)
        nsd_no = data.get('nsd_no')
        supplier = data.get('supplier')
        date = data.get('date')
        qty = data.get('qty')
        sell_rate = request.get('sell_rate')
        sell_amount = request.get('sell_amount')
        purchase_rate = request.get('purchase_rate')
        purchase_amount = request.get('purchase_amount')
        description = data.get('description')
        type_value = data.get('type')
        customer = None
        if type_value == 'customers':
            customer = get_object_or_404(Customers, id=supplier) if supplier else None
            supplier = None 
        else:  
            customer = None
            supplier = get_object_or_404(Suppliers, id=supplier) if supplier else None
        if data.get('nsd_id'):
            nsd = get_object_or_404(NSDs, id=data.get('nsd_id'))
            nsd.nsd_no = nsd_no
            nsd.supplier = supplier
            nsd.date = date
            nsd.qty = qty
            nsd.sell_rate = sell_rate
            nsd.sell_amount = sell_amount
            nsd.purchase_rate = purchase_rate
            nsd.purchase_amount = purchase_amount
            nsd.description = description
            nsd.type = type_value
            nsd.customer = customer
            if not nsd.hold:
                nsd.hold = False 
            nsd.save()
            return JsonResponse({'status':'success','nsd_id':nsd.id,'hold':nsd.hold})
        nsd = NSDs.objects.create(
            nsd_no=nsd_no,
            supplier=supplier,
            date=date,
            qty=qty,
            sell_rate=sell_rate,
            sell_amount=sell_amount,
            purchase_rate=purchase_rate,
            purchase_amount=purchase_amount,
            description=description,
            type=type_value,
            customer=customer,
            hold=True,
        )
        return JsonResponse({'status':'success','nsd_id':nsd.id,'hold':nsd.hold}) 
    
    
        


def getLastNSDNo():
    last_nsd_no = NSDs.objects.filter(is_active=True).order_by('-nsd_no').first() 
    
    if last_nsd_no and last_nsd_no.nsd_no.isdigit():
        new_nsd_no = int(last_nsd_no.nsd_no) + 1
    else:
        new_nsd_no = 1
    return new_nsd_no


def nsd_no(request):
    new_nsd_no = getLastNSDNo()
    return JsonResponse({'nsd_no': new_nsd_no})


def nsds_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    nsds = []
    if from_date and to_date:
        nsds = NSDs.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True
        )
    nsdData = []
    total_qty = 0
    total_amount = 0
    rate_sum = 0
    count = 0
    for nsd in nsds:
        nsdData.append({ 
            'id':nsd.id,
            'nsd_no':nsd.nsd_no,
            'supplier':nsd.supplier.name if nsd.supplier else '',
            'supplier_id':nsd.supplier.id if nsd.supplier else '',
            'customer':nsd.customer.name if nsd.customer else '',
            'customer_id':nsd.customer.id if nsd.customer else '',
            'date':str(nsd.date),
            'qty':nsd.qty,
            'sell_rate':nsd.sell_rate,
            'sell_amount':nsd.sell_amount,
            'purchase_rate':nsd.purchase_rate,
            'purchase_amount':nsd.purchase_amount,
            'description':nsd.description if nsd.description else '', 
            'type':nsd.which_type if nsd.which_type else '',
        })
        total_qty += nsd.qty
        total_sell_amount += nsd.sell_amount
        sell_rate_sum += nsd.sell_rate
        total_purchase_amount += nsd.purchase_amount
        purchase_rate_sum += nsd.purchase_rate
        count += 1
    sell_rate_avg = sell_rate_sum / count if count > 0 else 0
    purchase_rate_avg = purchase_rate_sum / count if count > 0 else 0
    return JsonResponse({'nsds': nsdData, 'total_qty': total_qty, 'total_amount': total_amount, 'sell_rate_avg': sell_rate_avg, 'purchase_rate_avg': purchase_rate_avg})


def delete_nsd(request):
    pk = request.GET.get('id') 
    nsd = get_object_or_404(NSDs, id=pk)
    nsd.is_active = False
    nsd.save()
    return JsonResponse({'status':'success','message':'nsd deleted successfully'})