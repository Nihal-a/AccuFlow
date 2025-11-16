import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Sales,Suppliers,Customers,Godowns
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient, update_ledger

class SaleEntryView(View):
    def get(self,request):
        sales = Sales.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        saleData = []
        for sale in sales:
            print(sale.which_type) 
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
        suppliers = Suppliers.objects.filter(is_active=True,client=getClient(request.user))
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        godowns = Godowns.objects.filter(is_active=True,client=getClient(request.user))
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
            'sales':saleData,
            'suppliers':suppliersData,
            'customers':customersData,
            'godowns':godowns,
            'last_sale_no':getLastSaleNo(client=getClient(request.user)),
        }
        return render(request,'sale_entry/sale_entry.html',context)
    
    

class SaleAddView(View):
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
        count = 0
        for id in sale_ids:
            customer = None 
            if types[count] == 'customers':
                supplier = None
                customer = get_object_or_404(Customers, id=customer_ids[count]) if customer_ids[count] else None
            else:
                customer = None
                supplier = get_object_or_404(Suppliers, id=customer_ids[count]) if customer_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            sale = Sales.objects.get(id=id)
            sale.supplier = supplier
            sale.godown = godown
            sale.date = dates[count]
            sale.qty = qtys[count]
            sale.amount = amounts[count]
            sale.total_amount = total_amounts[count]    
            sale.hold = False
            sale.customer = customer
            sale.client=getClient(request.user)
            sale.save()  
            count += 1
        return redirect('sale')


    


class SaleHold(View):
    def post(self,request):
        data = json.loads(request.body)
        sale_no = data.get('sale_no')
        supplier = data.get('customer')
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
        if data.get('sale_id'):
            sale = get_object_or_404(Sales, id=data.get('sale_id'))
            
            update_ledger(
                where=sale.party, 
                to=sale.godown,
                old_purchase=sale.total_amount,
                old_sale=sale.total_amount,
                new_purchase=0,
                new_sale=0
            )
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
            update_ledger(
                where=seller,
                to=godown,
                old_purchase=0, 
                old_sale=0,
                new_purchase=total_amount,
                new_sale=total_amount,
            )
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
        update_ledger(where=seller,to=godown,new_purchase=total_amount,new_sale=total_amount)
        return JsonResponse({'status':'success','sale_id':sale.id,'hold':sale.hold}) 
    
    
        


def getLastSaleNo(client):
    last_sale_no = Sales.objects.filter(is_active=True,client=client).order_by('-sale_no').first() 
    
    if last_sale_no and last_sale_no.sale_no.isdigit():
        new_sale_no = int(last_sale_no.sale_no) + 1
    else:
        new_sale_no = 1
    return new_sale_no


def sale_no(request):
    new_sale_no = getLastSaleNo(client=getClient(request.user))
    return JsonResponse({'sale_no': new_sale_no})


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
        )
    saleData = []
    total_qty = 0
    total_amount = 0
    rate_sum = 0
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


def delete_sale(request):
    pk = request.GET.get('id') 
    sale = get_object_or_404(Sales, id=pk)
    sale.is_active = False
    update_ledger(
        where=sale.party, 
        to=sale.godown,
        old_purchase=sale.total_amount,
        old_sale=sale.total_amount,
        new_purchase=0,
        new_sale=0
    )
    sale.save()
    return JsonResponse({'status':'success','message':'sale deleted successfully'})