from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q, Value, CharField, F
from django.utils import timezone
from datetime import datetime
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs
from core.views import getClient

class CustomerLedgerView(View):
    def get(self, request):
        customers = Customers.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'customer_ledger/customer_ledger.html', {'customers': customers, 'sort': 'Serial'})

    def post(self, request):
        customer_id = request.POST.get('customer')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        customers = Customers.objects.filter(is_active=True, client=client)

        context = {
            'customers': customers,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'customer': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'credit_total': 0,
            'debit_total': 0,
            'total_balance': 0,
            'open_balance': 0,
        }

        if not customer_id:
            return render(request, 'customer_ledger/customer_ledger.html', context)

        customer = get_object_or_404(Customers, id=customer_id)
        context['customer'] = customer

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(customer, client, date_from)
        else:
            opening_balance = (customer.open_debit or 0) - (customer.open_credit or 0)
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        purchases = Purchases.objects.filter(base_filter, date_filter, customer=customer)
        for p in purchases:
            desc = f"{p.godown.name}\n{p.description}" if sort != 'Remark' else p.description
            ledger_items.append({
                'transaction_no': str(p.purchase_no),
                'date': p.date,
                'type': 'PR',
                'description': desc,
                'qty': p.qty,
                'rate': p.amount,
                'credit': p.total_amount,
                'debit': 0,
                'created_at': p.created_at,
                'original_obj': p
            })

        sales = Sales.objects.filter(base_filter, date_filter, customer=customer)
        for s in sales:
            desc = f"{s.godown.name}\n{s.description}" if sort != 'Detailed' else s.description
            ledger_items.append({
                'transaction_no': str(s.sale_no),
                'date': s.date,
                'type': 'SL',
                'description': desc,
                'qty': s.qty,
                'rate': s.amount,
                'credit': 0,
                'debit': s.total_amount,
                'created_at': s.created_at,
                'original_obj': s
            })

        sender_nsds = NSDs.objects.filter(base_filter, date_filter, sender_customer=customer)
        for n in sender_nsds:
            desc = f"{n.receiver.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.sell_rate,
                'credit': n.sell_amount,
                'debit': 0,
                'created_at': n.created_at,
                'original_obj': n
            })

        receiver_nsds = NSDs.objects.filter(base_filter, date_filter, receiver_customer=customer)
        for n in receiver_nsds:
            desc = f"{n.sender.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.purchase_rate,
                'credit': 0,
                'debit': n.purchase_amount,
                'created_at': n.created_at,
                'original_obj': n
            })

        cashs = Cashs.objects.filter(base_filter, date_filter, customer=customer)
        for c in cashs:
            is_received = (c.transaction == 'Received')
            desc = c.cash_bank.name if sort != 'Remark' else c.description
            ledger_items.append({
                'transaction_no': str(c.cash_no),
                'date': c.date,
                'type': 'JL',
                'description': desc,
                'qty': '',
                'rate': c.amount,
                'credit': c.amount if is_received else 0,
                'debit': c.amount if not is_received else 0,
                'created_at': c.created_at,
                'original_obj': c
            })

        start_balance = 0
        if opening_flag != 'on':
             start_balance = opening_balance
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': customer.created_at.date() if customer.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'qty': '1',
                'rate': customer.open_balance,
                'credit': customer.open_credit,
                'debit': customer.open_debit,
                'balance': customer.open_balance, 
                'created_at': customer.created_at,
                'is_ob': True
             })
        
        ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

        if sort == 'Serial':
             ledger_items.sort(key=lambda x: x['transaction_no'])

        running_val = start_balance
        credit_sum = 0
        debit_sum = 0
        
        final_ledgers = []
        
        for item in ledger_items:
            c_val = float(item.get('credit') or 0)
            d_val = float(item.get('debit') or 0)
            
            if item.get('type') == 'OB':
                item['balance'] = start_balance
            else:
                running_val += (d_val - c_val)
                item['balance'] = running_val
                
                credit_sum += c_val
                debit_sum += d_val
            
            final_ledgers.append(item)
            
        if opening_flag == 'on':
            context['open_balance'] = 0

        context['ledgers'] = final_ledgers
        context['credit_total'] = credit_sum
        context['debit_total'] = debit_sum
        context['total_balance'] = running_val
        
        return render(request, 'customer_ledger/customer_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, customer, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, customer=customer, date__lt=date_limit)
        nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or 0
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or 0
        sender_sum = NSDs.objects.filter(nsd_base, sender_customer=customer).aggregate(s=Sum('sell_amount'))['s'] or 0
        receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=customer).aggregate(s=Sum('purchase_amount'))['s'] or 0
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or 0
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or 0
        
        transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
        
        static_ob = (customer.open_debit or 0) - (customer.open_credit or 0)
        
        return static_ob + transaction_balance