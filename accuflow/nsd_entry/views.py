import datetime
from django.shortcuts import render,redirect, get_object_or_404
from core.models import NSD,Customers,Suppliers
from django.views import View
from django.views.generic.edit import DeleteView

class NSDEntryView(View):
    def get(self,request):
        today = datetime.date.today()
        all_nsd = NSD.objects.filter(date=today)
        nsdData = []
        for nsd in all_nsd:
            nsdData.append({
                'id':nsd.id,
                'sale_no':nsd.nsd_no,
                'customer':nsd.customer.name if nsd.customer else '',
                'customer_id':nsd.customer.id if nsd.customer else '',
                'supplier':nsd.supplier.name if nsd.supplier else '',
                'supplier_id':nsd.supplier.id if nsd.supplier else '',
                'date':str(nsd.date),
                'qty':nsd.qty,
                'sell_rate':nsd.sell_rate,
                'purchase_rate':nsd.purchase_rate,
                'sell_amount':nsd.sell_amount,
                'purchase_amount':nsd.purchase_amount,
                'description':nsd.description if nsd.description else '', 
            })
        customers = Customers.objects.filter(is_active=True)
        Suppliers = Suppliers.objects.filter(is_active=True)
        context = {
            'nsd':nsdData,
            'customers':customers,
            'suppliers':Suppliers,
        }
        return render(request,'nsd_entry/nsd_entry.html',context)
    
    

# class NSDAddView(View):
#     def post(self,request):
#         today = datetime.date.today()
#         dates = request.POST.getlist('dates')
#         nsd_nos = request.POST.getlist('sales_nos')
#         purchase_amounts = request.POST.getlist('purchase_amounts')
#         purchase_amounts = request.POST.getlist('purchase_amounts')
#         total_amounts = request.POST.getlist('total_amounts')
#         qtys = request.POST.getlist('qtys')
#         amounts = request.POST.getlist('amounts')
#         customer_ids = request.POST.getlist('customers')
#         godown_ids = request.POST.getlist('godowns')
#         count = 0
#         for d in dates:
#             customer = get_object_or_404(Customers, id=customer_ids[count]) if customer_ids[count] else None
#             godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
#             Sales.objects.create(
#                 sales_no=sales_nos[count],
#                 customers=customer,
#                 godown=godown,
#                 date=dates[count],
#                 qty=qtys[count],
#                 amount=amounts[count],
#                 total_amount=total_amounts[count], 
#             )
#             count += 1
#         return redirect('sales')
        
