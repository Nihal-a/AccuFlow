from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
from core.models import Expenses, Commissions
from core.views import getClient
from core.authorization import get_object_for_user

class ExpenseLedgerView(View):
    def get(self, request):
        client = getClient(request.user)
        expenses = Expenses.objects.filter(is_active=True, client=client)
        return render(request, 'expense_ledger/expense_ledger.html', {'expenses': expenses})

    def post(self, request):
        expense_id = request.POST.get('expense')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        expenses = Expenses.objects.filter(is_active=True, client=client)

        opening_flag = request.POST.get('opening')
        
        context = {
            'expenses': expenses,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'expense': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'open_balance': Decimal('0.0000'),
            'total_amount': Decimal('0.0000'),
            'total_qty': Decimal('0.0000'),
        }

        if not expense_id:
            return render(request, 'expense_ledger/expense_ledger.html', context)

        # Authorization: Ensure expense belongs to user's client
        expense = get_object_for_user(Expenses, request.user, id=expense_id)
        context['expense'] = expense

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        opening_balance = Decimal('0.0000')
        if date_from:
            # Sum up all expenses before the selected date_from
            ob_filter = Q(is_active=True, hold=False, client=client, expense=expense, date__lt=date_from)
            ob_sum = Commissions.objects.filter(ob_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
            opening_balance = ob_sum

        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client, expense=expense)
        if date_from:
            base_filter &= Q(date__gte=date_from)
        if date_to:
            base_filter &= Q(date__lte=date_to)

        commissions = Commissions.objects.filter(base_filter)
        
        for c in commissions:
            ledger_items.append({
                'transaction_no': str(c.commission_no),
                'date': c.date,
                'type': 'EX',
                'godown': c.godown.name if c.godown else '-',
                'description': c.description or '',
                'qty': c.qty,
                'rate': c.amount,
                'amount': c.total_amount,
                'created_at': c.created_at,
                'original_obj': c
            })

        start_balance = Decimal('0.0000')
        if opening_flag != 'on':
             start_balance = Decimal(str(opening_balance))
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': date_from or datetime.min.date(),
                'type': 'OB',
                'godown': '-',
                'description': '',
                'qty': '-',
                'rate': '-',
                'amount': opening_balance,
                'created_at': None,
                'is_ob': True
             })
            
        # Sort chronologically
        min_dt = timezone.make_aware(datetime.min) if timezone.get_current_timezone() else datetime.min
        ledger_items.sort(key=lambda x: (x['date'], x.get('created_at') or min_dt))

        total_sum = Decimal('0.0000')
        qty_sum = Decimal('0.0000')
        
        final_ledgers = []
        sno = 1
        for item in ledger_items:
            if item.get('type') != 'OB':
                item['sno'] = sno
                sno += 1
            
            try:
                item_qty = Decimal(str(item.get('qty') or 0))
            except:
                item_qty = Decimal('0.0000')
                
            try:
                item_amount = Decimal(str(item.get('amount') or 0))
            except:
                item_amount = Decimal('0.0000')

            total_sum += item_amount
            qty_sum += item_qty
            final_ledgers.append(item)
            
        context['ledgers'] = final_ledgers
        context['has_transactions'] = len(final_ledgers) > 1 or (len(final_ledgers) == 1 and final_ledgers[0].get('type') != 'OB')
        context['total_amount'] = total_sum
        context['total_qty'] = qty_sum
        
        return render(request, 'expense_ledger/expense_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None
