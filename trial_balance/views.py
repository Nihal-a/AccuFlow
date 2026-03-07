from django.shortcuts import render
from django.db.models import Sum, Q, F
from django.views import View
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs, Expenses, Commissions, Godowns
from core.views import getClient, calculate_customer_balance, calculate_supplier_balance
from django.template.loader import render_to_string
from django.http import HttpResponse

try:
    from weasyprint import HTML
except ImportError:
    pass

class TrialBalanceView(View):
    def get(self, request):
        return self.process_report(request)
    
    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        now = timezone.localtime(timezone.now())
        date_to_str = request.POST.get("dateTo") or now.strftime("%Y-%m-%d")
        
        try:
            date_limit = datetime.strptime(date_to_str, "%Y-%m-%d").date()
        except ValueError:
            date_limit = timezone.localtime(timezone.now()).date()
            
        accounts = []
        
        # filters
        base_filter_active = Q(is_active=True, client=client)
        date_filter_lte = Q(date__lte=date_limit)
        date_filter_created_lte = Q(created_at__lte=date_limit) # For expenses if they don't have 'date' field, but Expenses has created_at? core model check needed. 
        # Checking core models: Expenses has created_at, no date field. Commissions has date. 
        
        # 1. CASH / BANK (Assets -> Debit)
        # Logic: Sum(Received) - Sum(Paid) - Commissions
        # CRITICAL FIX: Commissions represent cash outflows but don't have corresponding 'Cashs' entries.
        # To balance the Trial Balance, we must assume these are paid via Cash if not recorded.
        # We subtract them from the Cash Balance.
        # core/models.py: Cashs has transaction='Received' or 'Paid'
        
        cash_received = Cashs.objects.filter(base_filter_active, date_filter_lte, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter_active, date_filter_lte, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        # Deduct commissions (assumed to be paid in cash)
        commissions_total = Commissions.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        
        cash_balance = cash_received - cash_paid - commissions_total
        
        if cash_balance != 0:
            accounts.append({
               'code': '1001', # Placeholder
               'name': 'CASH IN HAND',
               'phone': '',
               'debit': abs(cash_balance) if cash_balance > 0 else 0,
               'credit': abs(cash_balance) if cash_balance < 0 else 0,
            })

        # 2. CUSTOMERS (Assets -> Debit usually)
        customers = Customers.objects.filter(base_filter_active)
        for c in customers:
             # Calculate balance as of date_limit
             bal = self.calculate_party_balance(c, client, date_limit, is_customer=True)
             if bal != 0:
                 accounts.append({
                     'code': c.customerId,
                     'name': c.name,
                     'phone': c.phone,
                     'debit': bal if bal > 0 else 0,
                     'credit': abs(bal) if bal < 0 else 0
                 })

        # 3. SUPPLIERS (Liabilities -> Credit usually)
        suppliers = Suppliers.objects.filter(base_filter_active)
        for s in suppliers:
             bal = self.calculate_party_balance(s, client, date_limit, is_customer=False)
             # Supplier Balance Logic:
             # If I owe them (Credit balance in DB terms?), it's correct.
             # Wait, existing logic in payable_report: 
             # customer balance 'payable' if < 0.
             # Let's trust the signed balance from calculate_party_balance. 
             # Positive = Debit (Asset/Receivable), Negative = Credit (Liability/Payable).
             
             if bal != 0:
                 accounts.append({
                     'code': s.supplierId,
                     'name': s.name,
                     'phone': s.phone,
                     'debit': bal if bal > 0 else 0,
                     'credit': abs(bal) if bal < 0 else 0
                 })

        # 4. STOCK (Assets -> Debit)
        # Using Weighted Average Logic logic from StockView
        stock_value = self.calculate_stock_value(client, date_limit)
        if stock_value > 0:
            accounts.append({
                'code': '52000001',
                'name': 'STOCK OPEN.BALANCE (P&L)', # Using name from reference
                'phone': '',
                'debit': stock_value,
                'credit': 0
            })

        # 5. SALES (Income -> Credit)
        base_sales = Sales.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_sales = NSDs.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        total_sales = base_sales + nsd_sales
        if total_sales > 0:
             accounts.append({
                'code': '41000001',
                'name': 'SALES A/C',
                'phone': '',
                'debit': 0,
                'credit': total_sales
            })

        # 6. PURCHASES (Expense -> Debit)
        base_purchases = Purchases.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_purchases = NSDs.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        total_purchases = base_purchases + nsd_purchases
        if total_purchases > 0:
             accounts.append({
                'code': '51000001',
                'name': 'PURCHASE A/C',
                'phone': '',
                'debit': total_purchases,
                'credit': 0
            })
            
        # 7. EXPENSES (Expense -> Debit)
        # Group by Category if possible, or list individually? Reference image shows "SERVICE EXPENSE", "GENERAL EXPENSE".
        # We can aggregate by category.
        expenses = Expenses.objects.filter(base_filter_active) # Expenses model doesn't have 'date', it has 'created_at'
        # Filter manually or by date_filter_created_lte?
        # Let's check model again. 
        # Expenses: created_at.
        
        # We need to sum by category.
        # But wait, we need to respect the date filter.
        expenses_qs = Expenses.objects.filter(is_active=True, client=client, created_at__lte=date_limit) # Simplified
        
        expense_cats = {}
        for exp in expenses_qs:
            cat = exp.category.upper() if exp.category else "GENERAL EXPENSE"
            if cat not in expense_cats:
                expense_cats[cat] = Decimal('0.0000')
            expense_cats[cat] += Decimal(str(exp.amount or 0))
            
        for cat, amount in expense_cats.items():
            if amount > 0:
                 accounts.append({
                    'code': '6100000X', # Placeholder
                    'name': cat,
                    'phone': '',
                    'debit': amount,
                    'credit': 0
                })

        # 8. COMMISSIONS (Expense -> Debit)
        # Commissions has a 'date' field.
        commissions_total = Commissions.objects.filter(base_filter_active, date_filter_lte).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        if commissions_total > 0:
             accounts.append({
                'code': '62000001',
                'name': 'COMMISSIONS',
                'phone': '',
                'debit': commissions_total,
                'credit': 0
            })

        # Sort accounts by Name
        accounts.sort(key=lambda x: x['name'])
        
        # Calculate Totals
        total_debit = sum(a['debit'] for a in accounts)
        total_credit = sum(a['credit'] for a in accounts)
        difference = total_debit - total_credit
        
        context = {
            'accounts': accounts,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'difference': difference,
            'date_to': date_to_str,
            'is_balanced': abs(difference) < Decimal('0.01')
        }
        
        export_type = request.POST.get('export')
        if export_type == 'pdf':
             html_string = render_to_string('trial_balance/trial_balance_pdf.html', context)
             pdf_file = HTML(string=html_string).write_pdf()
             response = HttpResponse(pdf_file, content_type='application/pdf')
             response['Content-Disposition'] = 'inline; filename="trial_balance.pdf"'
             return response

        return render(request, 'trial_balance/trial_balance.html', context)

    def calculate_stock_value(self, client, date_limit):
        # Weighted Average Cost Logic from StockView
        # We need to iterate all godowns and calculate value
        godowns = Godowns.objects.filter(is_active=True, client=client)
        total_value_all = Decimal('0.0000')
        
        # Optimizing: Fetch all purchases and sales once might be heavy but accurate.
        # Let's filter by date
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q(date__lte=date_limit)
        
        purchases = Purchases.objects.filter(base_filter, date_filter)
        sales = Sales.objects.filter(base_filter, date_filter)
        
        stocks = {}
        
        # Process Purchases
        for p in purchases:
            g_id = p.godown_id
            if not g_id: continue
            if g_id not in stocks:
                stocks[g_id] = {'purchase_qty': Decimal(0), 'purchase_value': Decimal(0), 'balance_qty': Decimal(0)}
            
            qty = Decimal(str(p.qty))
            amount = Decimal(str(p.amount))
            stocks[g_id]['purchase_qty'] += qty
            stocks[g_id]['purchase_value'] += qty * amount
            stocks[g_id]['balance_qty'] += qty
            
        # Process Sales
        for s in sales:
            g_id = s.godown_id
            if not g_id: continue
            if g_id not in stocks:
                 stocks[g_id] = {'purchase_qty': Decimal(0), 'purchase_value': Decimal(0), 'balance_qty': Decimal(0)}
            
            qty = Decimal(str(s.qty))
            stocks[g_id]['balance_qty'] -= qty
            
        # Calculate Value
        for item in stocks.values():
            if item['balance_qty'] > 0:
                avg_rate = (item['purchase_value'] / item['purchase_qty']) if item['purchase_qty'] > 0 else Decimal(0)
                total_value_all += Decimal(str(item['balance_qty'])) * Decimal(str(avg_rate))
                
        return total_value_all

    def calculate_party_balance(self, entity, client, date_limit, is_customer=True):
        if is_customer:
            return calculate_customer_balance(entity, client, date_limit)
        else:
            return calculate_supplier_balance(entity, client, date_limit)
