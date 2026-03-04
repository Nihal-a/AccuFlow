from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q, Value, CharField, F
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
from core.models import Suppliers, Purchases, Sales, NSDs, Cashs, Godowns
from core.views import getClient
from core.authorization import get_object_for_user
from django.http import JsonResponse

class SupplierLedgerView(View):
    def get(self, request):
        suppliers = Suppliers.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'supplier_ledger/supplier_ledger.html', {'suppliers': suppliers, 'sort': 'Serial'})

    def post(self, request):
        supplier_id = request.POST.get('supplier')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)

        context = {
            'suppliers': suppliers,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'supplier': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'credit_total': Decimal('0.0000'),
            'debit_total': Decimal('0.0000'),
            'total_balance': Decimal('0.0000'),
            'open_balance': Decimal('0.0000'),
        }

        if not supplier_id:
            return render(request, 'supplier_ledger/supplier_ledger.html', context)

        # Authorization: Ensure supplier belongs to user's client
        supplier = get_object_for_user(Suppliers, request.user, id=supplier_id)
        context['supplier'] = supplier

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(supplier, client, date_from)
        else:
            opening_balance = supplier.open_debit - supplier.open_credit
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        purchases = Purchases.objects.filter(base_filter, date_filter, supplier=supplier)
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

        sales = Sales.objects.filter(base_filter, date_filter, supplier=supplier)
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

        sender_nsds = NSDs.objects.filter(base_filter, date_filter, sender_supplier=supplier)
        for n in sender_nsds:
            desc = f"{n.receiver.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.purchase_rate,
                'credit': n.purchase_amount,
                'debit': 0,
                'created_at': n.created_at,
                'original_obj': n
            })

        receiver_nsds = NSDs.objects.filter(base_filter, date_filter, receiver_supplier=supplier)
        for n in receiver_nsds:
            desc = f"{n.sender.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.sell_rate,
                'credit': 0,
                'debit': n.sell_amount,
                'created_at': n.created_at,
                'original_obj': n
            })

        cashs = Cashs.objects.filter(base_filter, date_filter, supplier=supplier)
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

        start_balance = Decimal('0.0000')
        if opening_flag != 'on':
             start_balance = Decimal(str(opening_balance))
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': supplier.created_at.date() if supplier.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'qty': '1',
                'rate': supplier.open_balance,
                'credit': supplier.open_credit,
                'debit': supplier.open_debit,
                'balance': supplier.open_balance, 
                'created_at': supplier.created_at,
                'is_ob': True
             })
        
        min_dt = timezone.make_aware(datetime.min) if timezone.get_current_timezone() else datetime.min
        ledger_items.sort(key=lambda x: (x['date'], x.get('created_at') or min_dt))

        if sort == 'Serial':
             ledger_items.sort(key=lambda x: (x['date'], x.get('created_at') or min_dt))

        running_val = start_balance
        credit_sum = Decimal('0.0000')
        debit_sum = Decimal('0.0000')
        
        final_ledgers = []
        
        for item in ledger_items:
            c_val = Decimal(str(item.get('credit') or 0))
            d_val = Decimal(str(item.get('debit') or 0))
            
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



        sno = 1
        for item in final_ledgers:
            if item.get('type') != 'OB':
                item['sno'] = sno
                sno += 1

        context['ledgers'] = final_ledgers
        context['has_transactions'] = any(item.get('type') != 'OB' for item in final_ledgers)
        context['credit_total'] = credit_sum
        context['debit_total'] = debit_sum
        context['total_balance'] = running_val
        
        return render(request, 'supplier_ledger/supplier_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, supplier, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, supplier=supplier, date__lt=date_limit)
        nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sender_sum = NSDs.objects.filter(nsd_base, sender_supplier=supplier).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        receiver_sum = NSDs.objects.filter(nsd_base, receiver_supplier=supplier).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        transaction_balance = (purchases_sum + sender_sum + cash_received) - (sales_sum + receiver_sum + cash_paid)
        
        static_ob = supplier.open_credit - supplier.open_debit
        
        return static_ob + transaction_balance