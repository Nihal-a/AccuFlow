from django.shortcuts import render,redirect, get_object_or_404
from core.models import CashBanks, Cashs
from django.views import View
from core.views import getClient
from django.db.models import Sum, Q 
from datetime import datetime
from decimal import Decimal

class CashBankView(View):
    def get(self, request):
        client = getClient(request.user)
        cashbanks = CashBanks.objects.filter(is_active=True, client=client)
        
        data = []
        total_balance_all = Decimal('0.0000')

        for cb in cashbanks:
            # Calculate total received
            received = Cashs.objects.filter(
                cash_bank=cb, 
                transaction='Received', 
                is_active=True, 
                hold=False,
                client=client
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.0000')

            # Calculate total paid
            paid = Cashs.objects.filter(
                cash_bank=cb, 
                transaction='Paid', 
                is_active=True, 
                hold=False,
                client=client
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.0000')

            balance = received - paid
            
            data.append({
                'obj': cb,
                'received': received,
                'paid': paid,
                'balance': balance
            })
            
            total_balance_all += balance

        context = {
            'cashbank_data': data,
            'total_balance_all': total_balance_all
        }
        return render(request, 'cashbank_balance/cashbank_balance.html', context)


class CashBankLedgerView(View):
    def get(self, request):
        cashbanks = CashBanks.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'cashbank_balance/cashbank_ledger.html', {'cashbanks': cashbanks, 'sort': 'Serial'})

    def post(self, request):
        cashbank_id = request.POST.get('cashbank')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        cashbanks = CashBanks.objects.filter(is_active=True, client=client)

        context = {
            'cashbanks': cashbanks,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'cashbank': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'recep_total': Decimal('0.0000'),
            'pay_total': Decimal('0.0000'),
            'total_balance': Decimal('0.0000'),
            'open_balance': Decimal('0.0000'),
        }

        if not cashbank_id:
            return render(request, 'cashbank_balance/cashbank_ledger.html', context)

        cashbank = get_object_or_404(CashBanks, id=cashbank_id)
        context['cashbank'] = cashbank

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(cashbank, client, date_from)
        else:
            opening_balance = Decimal('0.0000') # No opening balance field
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client, cash_bank=cashbank)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        # Cash Transactions
        cashs = Cashs.objects.filter(base_filter, date_filter)
        for c in cashs:
            desc = c.description if sort != 'Detailed' else c.description
            is_received = (c.transaction == 'Received')
            ledger_items.append({
                'transaction_no': str(c.cash_no),
                'date': c.date,
                'type': 'Cash',
                'description': desc,
                'recep': c.amount if is_received else 0,
                'pay': c.amount if not is_received else 0,
                'created_at': c.created_at,
                'original_obj': c
            })

        start_balance = Decimal('0.0000')
        if opening_flag != 'on':
             start_balance = opening_balance
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': cashbank.created_at.date() if cashbank.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'recep': '',
                'pay': '',
                'balance': start_balance, 
                'created_at': cashbank.created_at,
                'is_ob': True
             })
        
        ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

        running_val = start_balance
        recep_sum = Decimal('0.0000')
        pay_sum = Decimal('0.0000')
        
        final_ledgers = []
        
        for item in ledger_items:
            in_q = Decimal(str(item.get('recep') or 0))
            out_q = Decimal(str(item.get('pay') or 0))
            
            if item.get('type') == 'OB':
                item['balance'] = start_balance
            else:
                running_val += (in_q - out_q) # Receipt maps to Debit, Payment to Credit. Balance = Dr - Cr.
                item['balance'] = running_val
                
                recep_sum += in_q
                pay_sum += out_q
            
            final_ledgers.append(item)
            
        if opening_flag == 'on':
            context['open_balance'] = 0

        context['ledgers'] = final_ledgers
        context['recep_total'] = recep_sum
        context['pay_total'] = pay_sum
        context['total_balance'] = running_val
        
        return render(request, 'cashbank_balance/cashbank_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, cashbank, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, cash_bank=cashbank, date__lt=date_limit)
        
        received_sum = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        paid_sum = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        # Balance = Received - Paid
        balance = received_sum - paid_sum
        
        return balance
