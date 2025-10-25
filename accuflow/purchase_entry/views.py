import datetime
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Purchases,Suppliers,Customers,Godowns
from django.views import View
from django.views.generic.edit import DeleteView

class PurchaseEntryView(View):
    def get(self,request):
        today = datetime.date.today()
        purchases = Purchases.objects.filter(date=today)
        purchaseData = []
        for purchase in purchases:
            purchaseData.append({
                'id':purchase.id,
                'purchase_no':purchase.purchase_no,
                'supplier':purchase.supplier.name if purchase.supplier else '',
                'supplier_id':purchase.supplier.id if purchase.supplier else '',
                'customer':purchase.customers.name if purchase.customers else '',
                'customer_id':purchase.customers.id if purchase.customers else '',
                'godown':purchase.godown.name if purchase.godown else '',
                'godown_id':purchase.godown.id if purchase.godown else '',
                'date':str(purchase.date),
                'qty':purchase.qty,
                'amount':purchase.amount,
                'total_amount':purchase.total_amount,
                'description':purchase.description if purchase.description else '', 
            })
        suppliers = Suppliers.objects.filter(is_active=True)
        customers = Customers.objects.filter(is_active=True)
        godowns = Godowns.objects.filter(is_active=True)
        context = {
            'purchases':purchaseData,
            'suppliers':suppliers,
            'customers':customers,
            'godowns':godowns,
        }
        return render(request,'purchase_entry/purchase_entry.html',context)
    
    

class PurchaseAddView(View):
    def post(self,request):
        today = datetime.date.today()
        dates = request.POST.getlist('dates')
        purchase_nos = request.POST.getlist('purchase_nos')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        supplier_ids = request.POST.getlist('suppliers')
        customer_ids = request.POST.getlist('customers')
        godown_ids = request.POST.getlist('godowns')
        print(supplier_ids)
        Purchases.objects.filter(date=today).delete()
        count = 0
        for d in dates:
            
            supplier = get_object_or_404(Suppliers, id=supplier_ids[count]) if supplier_ids[count] else None
            # customer = get_object_or_404(Customers, id=customer_ids[count]) if customer_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            Purchases.objects.create(
                purchase_no=purchase_nos[count],
                supplier=supplier,
                # customers=customer,
                godown=godown,
                date=dates[count],
                qty=qtys[count],
                amount=amounts[count],
                total_amount=total_amounts[count], 
            )
            count += 1
        return redirect('purchase')
        
