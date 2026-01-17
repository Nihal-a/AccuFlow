from django.shortcuts import render
from django.views import View
from django.db.models import Sum, Q
from datetime import datetime
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs
from core.views import getClient

class PayableReportView(View):
    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        date_limit = None
        if date_to_str:
            try:
                date_limit = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        payables = []
        
        # 1. Customers
        customers = Customers.objects.filter(is_active=True, client=client)
        for c in customers:
            if date_limit:
                balance = self.calculate_balance(c, client, date_limit, is_customer=True)
            else:
                balance = c.balance 

            if balance < 0:
                payables.append({
                    'code': c.customerId,
                    'name': c.name,
                    'phone': c.phone,
                    'amount': abs(balance), 
                    'type': 'customer'
                })

        # 2. Suppliers
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        for s in suppliers:
            if date_limit:
                balance = self.calculate_balance(s, client, date_limit, is_customer=False)
            else:
                balance = s.balance 

            if balance < 0:
                payables.append({
                    'code': s.supplierId,
                    'name': s.name,
                    'phone': s.phone,
                    'amount': abs(balance),
                    'type': 'supplier'
                })

        payables.sort(key=lambda x: x['name'])

        total_amount = sum(item['amount'] for item in payables)

        context = {
            'payables': payables,
            'total_amount': total_amount,
            'date_from': date_from_str,
            'date_to': date_to_str,
        }
        return render(request, 'payable_report/payable_report.html', context)

    def calculate_balance(self, entity, client, date_limit, is_customer=True):
        if is_customer:
            base_filter = Q(is_active=True, hold=False, client=client, customer=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_customer=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_customer=entity, date__lte=date_limit)
        else:
            base_filter = Q(is_active=True, hold=False, client=client, supplier=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_supplier=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_supplier=entity, date__lte=date_limit)

        purchases = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or 0
        sales = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or 0
        nsd_sender_amt = NSDs.objects.filter(nsd_sender_filter).aggregate(s=Sum('sell_amount'))['s'] or 0
        nsd_receiver_amt = NSDs.objects.filter(nsd_receiver_filter).aggregate(s=Sum('purchase_amount'))['s'] or 0
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or 0
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or 0
        
        debit_sum = sales + nsd_receiver_amt + cash_paid
        credit_sum = purchases + nsd_sender_amt + cash_received
        
        static_ob = (entity.open_debit or 0) - (entity.open_credit or 0)
        
        return static_ob + (debit_sum - credit_sum)
