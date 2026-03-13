from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from core.models import Suppliers, Customers, Godowns, Purchases, Sales, NSDs, Cashs, StockTransfers, Commissions
from core.views import getClient
from core.authorization import get_object_for_user

class GeneralLedgerView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        customers = Customers.objects.filter(is_active=True, client=client)
        godowns = Godowns.objects.filter(is_active=True, client=client)
        
        context = {
            'suppliers': suppliers,
            'customers': customers,
            'godowns': godowns,
            'sort': 'Serial',
            'party_type': 'supplier' # Default
        }
        return render(request, 'general_ledger/general_ledger.html', context)

    def post(self, request):
        party_selection = request.POST.get('party') # Format: "type_id" e.g "supplier_15"
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        
        # Re-fetch lists for the dropdowns
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        customers = Customers.objects.filter(is_active=True, client=client)
        godowns = Godowns.objects.filter(is_active=True, client=client)

        context = {
            'suppliers': suppliers,
            'customers': customers,
            'godowns': godowns,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'party_selection': party_selection,
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'credit_total': Decimal('0.0000'),
            'debit_total': Decimal('0.0000'),
            'total_balance': Decimal('0.0000'),
            'open_balance': Decimal('0.0000'),
        }

        if not party_selection:
            return render(request, 'general_ledger/general_ledger.html', context)

        try:
            party_type, party_id = party_selection.split('_')
        except ValueError:
            return render(request, 'general_ledger/general_ledger.html', context)

        party = None
        if party_type == 'supplier':
            party = get_object_for_user(Suppliers, request.user, id=party_id)
        elif party_type == 'customer':
            party = get_object_for_user(Customers, request.user, id=party_id)
        elif party_type == 'godown':
            party = get_object_for_user(Godowns, request.user, id=party_id)
            
        context['selected_party'] = party
        context['selected_party_type'] = party_type # Helper for template if needed

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(party, party_type, client, date_from)
        else:
            if party_type == 'godown':
                # For Godown, balance is quantity based (Dr - Cr) usually, but logic in godown_ledger was (OpenDr - OpenCr)
                opening_balance = party.open_debit - party.open_credit
            else:
                 # Standard Financial: (Dr - Cr) for Asset/Exp, (Cr - Dr) for Liab/Inc? 
                 # Existing SupplierLedger uses: (open_debit - open_credit).
                 # Supplier is usually Credit balance. Let's stick to the formula used in supplier_ledger.py:
                 # opening_balance = (supplier.open_debit or 0) - (supplier.open_credit or 0)
                opening_balance = party.open_debit - party.open_credit
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        if party_type == 'supplier':
            self.get_supplier_transactions(party, base_filter, date_filter, sort, ledger_items)
        elif party_type == 'customer':
            self.get_customer_transactions(party, base_filter, date_filter, sort, ledger_items)
        elif party_type == 'godown':
             self.get_godown_transactions(party, base_filter, date_filter, sort, ledger_items)

        # Opening Balance Item
        start_balance = Decimal('0.0000')
        if opening_flag != 'on':
             start_balance = Decimal(str(opening_balance))
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': party.created_at.date() if party.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'qty': '1',
                'rate': party.open_balance, # Note: godown uses 'open_balance' field too?
                'credit': party.open_credit,
                'debit': party.open_debit,
                'balance': party.open_balance if hasattr(party, 'open_balance') else Decimal('0.0000'), 
                'created_at': party.created_at,
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
                # Running balance logic:
                # For Supplier/Customer: Debit increases, Credit decreases (Asset/Exp nature?) or reverse?
                # supplier_ledger.py: running_val += (d_val - c_val)
                # This implies Debit is positive, Credit is negative.
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
        
        return render(request, 'general_ledger/general_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, party, party_type, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, date__lt=date_limit)
        
        if party_type == 'supplier':
            # Logic from supplier_ledger
             s_filter = base_filter & Q(supplier=party)
             nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)
             
             purchases_sum = Purchases.objects.filter(s_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
             sales_sum = Sales.objects.filter(s_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
             sender_sum = NSDs.objects.filter(nsd_base, sender_supplier=party).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
             receiver_sum = NSDs.objects.filter(nsd_base, receiver_supplier=party).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
             
             cash_received = Cashs.objects.filter(s_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
             cash_paid = Cashs.objects.filter(s_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
             
             transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
             static_ob = party.open_debit - party.open_credit
             return static_ob + transaction_balance

        elif party_type == 'customer':
             # Logic from customer_ledger
             c_filter = base_filter & Q(customer=party)
             nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)

             purchases_sum = Purchases.objects.filter(c_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
             sales_sum = Sales.objects.filter(c_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
             sender_sum = NSDs.objects.filter(nsd_base, sender_customer=party).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
             receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=party).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
             
             cash_received = Cashs.objects.filter(c_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
             cash_paid = Cashs.objects.filter(c_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
             
             transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
             static_ob = party.open_debit - party.open_credit
             return static_ob + transaction_balance

        elif party_type == 'godown':
            # Logic for godown (Quantity based)
            # Purchase -> In (Debit)
            # Sale -> Out (Credit)
            # Transfer From -> Out (Credit)
            # Transfer To -> In (Debit)
            
            g_filter = base_filter & Q(godown=party)
            transfer_filter_from = Q(is_active=True, hold=False, client=client, transfer_from=party, date__lt=date_limit)
            transfer_filter_to = Q(is_active=True, hold=False, client=client, transfer_to=party, date__lt=date_limit)
            
            purchases_qty = Purchases.objects.filter(g_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
            sales_qty = Sales.objects.filter(g_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
            commissions_qty = Commissions.objects.filter(g_filter).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
            
            transfers_out = StockTransfers.objects.filter(transfer_filter_from).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
            transfers_in = StockTransfers.objects.filter(transfer_filter_to).aggregate(s=Sum('qty'))['s'] or Decimal('0.0000')
            
            # Debit (In) - Credit (Out)
            transaction_balance = (purchases_qty + transfers_in) - (sales_qty + transfers_out + commissions_qty)
            static_ob = party.open_debit - party.open_credit
            return static_ob + transaction_balance
            
        return Decimal('0.0000')

    def get_supplier_transactions(self, supplier, base_filter, date_filter, sort, ledger_items):
        # ... logic from supplier_ledger ...
        purchases = Purchases.objects.filter(base_filter, date_filter, supplier=supplier).select_related('godown')
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
            
        sales = Sales.objects.filter(base_filter, date_filter, supplier=supplier).select_related('godown')
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

        cashs = Cashs.objects.filter(base_filter, date_filter, supplier=supplier).select_related('cash_bank')
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

    def get_customer_transactions(self, customer, base_filter, date_filter, sort, ledger_items):
        # ... logic from customer_ledger ...
        purchases = Purchases.objects.filter(base_filter, date_filter, customer=customer).select_related('godown')
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

        sales = Sales.objects.filter(base_filter, date_filter, customer=customer).select_related('godown')
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
                'rate': n.purchase_rate,
                'credit': n.purchase_amount,
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
                'rate': n.sell_rate,
                'credit': 0,
                'debit': n.sell_amount,
                'created_at': n.created_at,
                'original_obj': n
            })

        cashs = Cashs.objects.filter(base_filter, date_filter, customer=customer).select_related('cash_bank')
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

    def get_godown_transactions(self, godown, base_filter, date_filter, sort, ledger_items):
        # Godown logic: Debit = In, Credit = Out. Value is Qty.
        
        # Purchases (In -> Debit)
        # Note: In godown_ledger logic it was 'debit': p.qty
        purchases = Purchases.objects.filter(base_filter, date_filter, godown=godown).select_related('supplier', 'customer')
        for p in purchases:
            supplier_name = p.supplier.name if p.supplier else (p.customer.name if hasattr(p, 'customer') and p.customer else '')
            desc = f"{supplier_name}\n{p.description}" if sort != 'Remark' else (p.description or "")
            ledger_items.append({
                'transaction_no': str(p.purchase_no),
                'date': p.date,
                'type': 'PR',
                'description': desc,
                'qty': p.qty,
                'rate': p.amount,
                'credit': 0,
                'debit': p.qty, # In
                'created_at': p.created_at,
                'original_obj': p
            })

        # Sales (Out -> Credit)
        sales = Sales.objects.filter(base_filter, date_filter, godown=godown).select_related('supplier', 'customer')
        for s in sales:
            customer_name = s.customer.name if s.customer else (s.supplier.name if hasattr(s, 'supplier') and s.supplier else '')
            desc = f"{customer_name}\n{s.description}" if sort != 'Detailed' else (s.description or "")
            ledger_items.append({
                'transaction_no': str(s.sale_no),
                'date': s.date,
                'type': 'SL',
                'description': desc,
                'qty': s.qty,
                'rate': s.amount,
                'credit': s.qty, # Out
                'debit': 0,
                'created_at': s.created_at,
                'original_obj': s
            })

        # Stock Transfers FROM this godown (Out -> Credit)
        transfer_base = Q(is_active=True, hold=False, client=godown.client)
        transfers_out = StockTransfers.objects.filter(transfer_base, date_filter, transfer_from=godown).select_related('transfer_to')
        for t in transfers_out:
            desc = f"To: {t.transfer_to.name if t.transfer_to else ''}\n{t.description}" if sort != 'Remark' else (t.description or "")
            ledger_items.append({
                 'transaction_no': str(t.transfer_no),
                 'date': t.date,
                 'type': 'TR',
                 'description': desc,
                 'qty': t.qty,
                 'rate': '',
                 'credit': t.qty, # Out
                 'debit': 0,
                 'created_at': t.created_at,
                 'original_obj': t
            })

        # Stock Transfers TO this godown (In -> Debit)
        transfers_in = StockTransfers.objects.filter(transfer_base, date_filter, transfer_to=godown).select_related('transfer_from')
        for t in transfers_in:
            desc = f"From: {t.transfer_from.name if t.transfer_from else ''}\n{t.description}" if sort != 'Remark' else (t.description or "")
            ledger_items.append({
                 'transaction_no': str(t.transfer_no),
                 'date': t.date,
                 'type': 'TR',
                 'description': desc,
                 'qty': t.qty,
                 'rate': '',
                 'credit': 0,
                 'debit': t.qty, # In
                 'created_at': t.created_at,
                 'original_obj': t
            })

        # Commissions (Out -> Credit, like sales)
        commissions = Commissions.objects.filter(base_filter, date_filter, godown=godown).select_related('expense')
        for c in commissions:
            expense_name = c.expense.category if c.expense else ''
            desc = f"{expense_name}\n{c.description}" if sort != 'Remark' else (c.description or "")
            ledger_items.append({
                 'transaction_no': str(c.commission_no),
                 'date': c.date,
                 'type': 'CM',
                 'description': desc,
                 'qty': c.qty,
                 'rate': c.amount,
                 'credit': c.qty, # Out
                 'debit': 0,
                 'created_at': c.created_at,
                 'original_obj': c
            })
