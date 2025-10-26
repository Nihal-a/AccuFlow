import datetime
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Sales,Customers,Godowns
from django.views import View
from django.views.generic.edit import DeleteView

class SalesEntryView(View):
    def get(self,request):
        today = datetime.date.today()
        sales = Sales.objects.filter(date=today)
        salesData = []
        for sale in sales:
            salesData.append({
                'id':sale.id,
                'sale_no':sale.sales_no,
                'customer':sale.customers.name if sale.customers else '',
                'customer_id':sale.customers.id if sale.customers else '',
                'godown':sale.godown.name if sale.godown else '',
                'godown_id':sale.godown.id if sale.godown else '',
                'date':str(sale.date),
                'qty':sale.qty,
                'amount':sale.amount,
                'total_amount':sale.total_amount,
                'description':sale.description if sale.description else '', 
            })
        customers = Customers.objects.filter(is_active=True)
        godowns = Godowns.objects.filter(is_active=True)
        context = {
            'sales':salesData,
            'customers':customers,
            'godowns':godowns,
        }
        return render(request,'sale_entry/sale_entry.html',context)
    
    

class SalesAddView(View):
    def post(self,request):
        today = datetime.date.today()
        dates = request.POST.getlist('dates')
        sales_nos = request.POST.getlist('sales_nos')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        customer_ids = request.POST.getlist('customers')
        godown_ids = request.POST.getlist('godowns')
        count = 0
        for d in dates:
            customer = get_object_or_404(Customers, id=customer_ids[count]) if customer_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            Sales.objects.create(
                sales_no=sales_nos[count],
                customers=customer,
                godown=godown,
                date=dates[count],
                qty=qtys[count],
                amount=amounts[count],
                total_amount=total_amounts[count], 
            )
            count += 1
        return redirect('sales')
        
