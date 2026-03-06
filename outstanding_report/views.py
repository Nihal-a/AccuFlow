from django.shortcuts import render
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Sum
from decimal import Decimal
from core.models import Customers, Suppliers, Sales, Purchases, NSDs
from core.views import getClient, calculate_customer_balance, calculate_supplier_balance

class OutstandingCustomerView(View):
    def get(self, request):
        client = getClient(request.user)
        customers = Customers.objects.filter(is_active=True, client=client).only('id', 'customerId', 'name', 'phone', 'balance').order_by('name')
        paginator = Paginator(customers, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        data = []
        for c in page_obj.object_list:
            balance = calculate_customer_balance(c, client)
            
            total_sales = Sales.objects.filter(is_active=True, client=client, customer=c).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
            total_purchases = Purchases.objects.filter(is_active=True, client=client, customer=c).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
            
            # NSD logic: Sender (Customer) = purchase_amount (credit), Receiver (Customer) = sell_amount (debit)
            total_nsd_sender = NSDs.objects.filter(is_active=True, client=client, sender_customer=c).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
            total_nsd_receiver = NSDs.objects.filter(is_active=True, client=client, receiver_customer=c).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
            
            total_trade = total_sales + total_purchases + total_nsd_sender + total_nsd_receiver
            
            data.append({
                'code': c.customerId,
                'name': c.name,
                'phone': c.phone,
                'total_trade': total_trade,
                'balance': balance
            })
        
        data.sort(key=lambda x: x['total_trade'], reverse=True)
        
        context = {
            'customers': data,
            'page_obj': page_obj
        }
        return render(request, 'outstanding_report/outstanding_customer.html', context)


class OutstandingSupplierView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = Suppliers.objects.filter(is_active=True, client=client).only('id', 'supplierId', 'name', 'phone', 'balance').order_by('name')
        paginator = Paginator(suppliers, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        data = []
        for s in page_obj.object_list:
            balance = calculate_supplier_balance(s, client)
            
            total_purchase = Purchases.objects.filter(is_active=True, client=client, supplier=s).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
            total_sales = Sales.objects.filter(is_active=True, client=client, supplier=s).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
            
            # NSD logic: Sender (Supplier) = purchase_amount, Receiver (Supplier) = sell_amount
            total_nsd_sender = NSDs.objects.filter(is_active=True, client=client, sender_supplier=s).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
            total_nsd_receiver = NSDs.objects.filter(is_active=True, client=client, receiver_supplier=s).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
            
            total_trade = total_purchase + total_sales + total_nsd_sender + total_nsd_receiver
            
            data.append({
                'code': s.supplierId,
                'name': s.name,
                'phone': s.phone,
                'total_trade': total_trade,
                'balance': balance
            })
        
        data.sort(key=lambda x: x['total_trade'], reverse=True)
        
        return render(request, 'outstanding_report/outstanding_supplier.html', {'suppliers': data, 'page_obj': page_obj})
