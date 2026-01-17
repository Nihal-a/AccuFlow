from django.shortcuts import render
from django.views import View
from django.db.models import Sum
from core.models import Customers, Suppliers, Sales, Purchases, NSDs
from core.views import getClient

class OutstandingCustomerView(View):
    def get(self, request):
        client = getClient(request.user)
        customers = Customers.objects.filter(is_active=True, client=client)
        data = []
        for c in customers:
            total_sales = Sales.objects.filter(is_active=True, client=client, customer=c).aggregate(s=Sum('total_amount'))['s'] or 0
            
            total_nsd_sender = NSDs.objects.filter(is_active=True, client=client, sender_customer=c).aggregate(s=Sum('sell_amount'))['s'] or 0
            total_nsd_receiver = NSDs.objects.filter(is_active=True, client=client, receiver_customer=c).aggregate(s=Sum('purchase_amount'))['s'] or 0
            
            total_trade = total_sales + total_nsd_sender + total_nsd_receiver
            
            data.append({
                'code': c.customerId,
                'name': c.name,
                'phone': c.phone,
                'total_trade': total_trade,
                'balance': c.balance
            })
        
        data.sort(key=lambda x: x['total_trade'], reverse=True)
        
        return render(request, 'outstanding_report/outstanding_customer.html', {'customers': data})


class OutstandingSupplierView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        data = []
        for s in suppliers:
            total_purchase = Purchases.objects.filter(is_active=True, client=client, supplier=s).aggregate(s=Sum('total_amount'))['s'] or 0
            
            total_nsd_sender = NSDs.objects.filter(is_active=True, client=client, sender_supplier=s).aggregate(s=Sum('sell_amount'))['s'] or 0
            total_nsd_receiver = NSDs.objects.filter(is_active=True, client=client, receiver_supplier=s).aggregate(s=Sum('purchase_amount'))['s'] or 0
            
            total_trade = total_purchase + total_nsd_sender + total_nsd_receiver
            
            data.append({
                'code': s.supplierId,
                'name': s.name,
                'phone': s.phone,
                'total_trade': total_trade,
                'balance': s.balance
            })
        
        data.sort(key=lambda x: x['total_trade'], reverse=True)
        
        return render(request, 'outstanding_report/outstanding_supplier.html', {'suppliers': data})
