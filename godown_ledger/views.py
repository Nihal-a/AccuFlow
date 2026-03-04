from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q, Value, CharField, F
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
from core.models import Customers, Godowns, Purchases, Sales, NSDs, Cashs, StockTransfers, Commissions
from core.views import getClient
from core.authorization import get_object_for_user
from django.http import JsonResponse

class GodownLedgerView(View):
    def get(self, request):
        godowns = Godowns.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'godown_ledger/godown_ledger.html', {'godowns': godowns, 'sort': 'Serial'})

    def post(self, request):
        godown_id = request.POST.get('godown')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        godowns = Godowns.objects.filter(is_active=True, client=client)

        context = {
            'godowns': godowns,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'godown': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'credit_total': Decimal('0.0000'),
            'debit_total': Decimal('0.0000'),
            'total_balance': Decimal('0.0000'),
            'open_balance': Decimal('0.0000'),
        }

        if not godown_id:
            return render(request, 'godown_ledger/godown_ledger.html', context)

        # Authorization: Ensure godown belongs to user's client
        godown = get_object_for_user(Godowns, request.user, id=godown_id)
        context['godown'] = godown

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(godown, client, date_from)
        else:
            opening_balance = (godown.open_debit or 0) - (godown.open_credit or 0)
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        purchases = Purchases.objects.filter(base_filter, date_filter, godown=godown)
        for p in purchases:
            supplier_name = p.supplier.name if p.supplier else (p.customer.name if hasattr(p, 'customer') and p.customer else '')
            desc = f"{supplier_name}\n{p.description}" if sort != 'Remark' else p.description
            ledger_items.append({
                'transaction_no': str(p.purchase_no),
                'date': p.date,
                'type': 'PR',
                'description': desc,
                'qty': p.qty,
                'rate': p.amount,
                'credit': 0,
                'debit': p.qty,
                'created_at': p.created_at,
                'original_obj': p
            })

        sales = Sales.objects.filter(base_filter, date_filter, godown=godown)
        for s in sales:
            customer_name = s.customer.name if s.customer else (s.supplier.name if hasattr(s, 'supplier') and s.supplier else '')
            desc = f"{customer_name}\n{s.description}" if sort != 'Detailed' else s.description
            ledger_items.append({
                'transaction_no': str(s.sale_no),
                'date': s.date,
                'type': 'SL',
                'description': desc,
                'qty': s.qty,
                'rate': s.amount,
                'credit': s.qty,
                'debit': 0,
                'created_at': s.created_at,
                'original_obj': s
            })

        # Stock Transfers OUT (credit = qty out)
        transfer_base = Q(is_active=True, hold=False, client=client)
        transfers_out = StockTransfers.objects.filter(transfer_base, date_filter, transfer_from=godown)
        for t in transfers_out:
            desc = f"To: {t.transfer_to.name if t.transfer_to else ''}" if sort != 'Remark' else t.description
            ledger_items.append({
                'transaction_no': str(t.transfer_no),
                'date': t.date,
                'type': 'ST',
                'description': desc,
                'qty': t.qty,
                'rate': '',
                'credit': t.qty,
                'debit': 0,
                'created_at': t.created_at,
                'original_obj': t
            })

        # Stock Transfers IN (debit = qty in)
        transfers_in = StockTransfers.objects.filter(transfer_base, date_filter, transfer_to=godown)
        for t in transfers_in:
            desc = f"From: {t.transfer_from.name if t.transfer_from else ''}" if sort != 'Remark' else t.description
            ledger_items.append({
                'transaction_no': str(t.transfer_no),
                'date': t.date,
                'type': 'ST',
                'description': desc,
                'qty': t.qty,
                'rate': '',
                'credit': 0,
                'debit': t.qty,
                'created_at': t.created_at,
                'original_obj': t
            })

        # Commissions (credit = qty out, like sales)
        commissions = Commissions.objects.filter(base_filter, date_filter, godown=godown)
        for c in commissions:
            expense_name = c.expense.category if c.expense else ''
            desc = f"{expense_name}\n{c.description}" if sort != 'Remark' else c.description
            ledger_items.append({
                'transaction_no': str(c.commission_no),
                'date': c.date,
                'type': 'CM',
                'description': desc,
                'qty': c.qty,
                'rate': c.amount,
                'credit': c.qty,
                'debit': 0,
                'created_at': c.created_at,
                'original_obj': c
            })
        # sender_nsds = NSDs.objects.filter(base_filter, date_filter, sender_customer=customer)
        # for n in sender_nsds:
        #     desc = f"{n.receiver.name}\n{n.description}" if sort != 'Remark' else n.description
        #     ledger_items.append({
        #         'transaction_no': str(n.nsd_no),
        #         'date': n.date,
        #         'type': 'NS',
        #         'description': desc,
        #         'qty': n.qty,
        #         'rate': n.sell_rate,
        #         'credit': n.sell_amount,
        #         'debit': 0,
        #         'created_at': n.created_at,
        #         'original_obj': n
        #     })

        # receiver_nsds = NSDs.objects.filter(base_filter, date_filter, receiver_customer=customer)
        # for n in receiver_nsds:
        #     desc = f"{n.sender.name}\n{n.description}" if sort != 'Remark' else n.description
        #     ledger_items.append({
        #         'transaction_no': str(n.nsd_no),
        #         'date': n.date,
        #         'type': 'NS',
        #         'description': desc,
        #         'qty': n.qty,
        #         'rate': n.purchase_rate,
        #         'credit': 0,
        #         'debit': n.purchase_amount,
        #         'created_at': n.created_at,
        #         'original_obj': n
        #     })

        # cashs = Cashs.objects.filter(base_filter, date_filter, customer=customer)
        # for c in cashs:
        #     is_received = (c.transaction == 'Received')
        #     desc = c.cash_bank.name if sort != 'Remark' else c.description
        #     ledger_items.append({
        #         'transaction_no': str(c.cash_no),
        #         'date': c.date,
        #         'type': 'JL',
        #         'description': desc,
        #         'qty': '',
        #         'rate': c.amount,
        #         'credit': c.amount if is_received else 0,
        #         'debit': c.amount if not is_received else 0,
        #         'created_at': c.created_at,
        #         'original_obj': c
        #     })

        start_balance = Decimal('0.0000')
        if opening_flag != 'on':
             start_balance = Decimal(str(opening_balance))
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': godown.created_at.date() if godown.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'qty': '1',
                'rate': godown.open_balance,
                'credit': godown.open_credit,
                'debit': godown.open_debit,
                'balance': godown.open_balance, 
                'created_at': godown.created_at,
                'is_ob': True
             })
        
        ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

        if sort == 'Serial':
             ledger_items.sort(key=lambda x: x['transaction_no'])

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
        context['has_transactions'] = len([l for l in final_ledgers if l.get('type') != 'OB']) > 0
        context['credit_total'] = credit_sum
        context['debit_total'] = debit_sum
        context['total_balance'] = running_val
        
        return render(request, 'godown_ledger/godown_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, godown, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, godown=godown, date__lt=date_limit)
        transfer_filter_from = Q(is_active=True, hold=False, client=client, transfer_from=godown, date__lt=date_limit)
        transfer_filter_to = Q(is_active=True, hold=False, client=client, transfer_to=godown, date__lt=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
        commissions_sum = Commissions.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
        
        transfers_in_sum = StockTransfers.objects.filter(transfer_filter_to).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
        transfers_out_sum = StockTransfers.objects.filter(transfer_filter_from).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
        
        transaction_balance = (purchases_sum + transfers_in_sum) - (sales_sum + transfers_out_sum + commissions_sum)
        
        static_ob = (godown.open_debit or Decimal('0.0000')) - (godown.open_credit or Decimal('0.0000'))
        
        return static_ob + transaction_balance
    