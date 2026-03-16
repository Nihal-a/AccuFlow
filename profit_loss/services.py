from django.db.models import Sum, Q, F
from decimal import Decimal, ROUND_HALF_UP
from core.models import Godowns, Purchases, Sales, Expenses, Commissions, NSDs, Cashs, Customers, Suppliers
from core.views import calculate_customer_balance, calculate_supplier_balance
import datetime

class StockService:
    @staticmethod
    def calculate_stock_value(client, date_limit):
        """
        Calculates the total value of stock across all godowns for a client as of a specific date.
        Uses Weighted Average Cost method. Includes Commissions and Stock Transfers.
        """
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q(date__lte=date_limit)
        
        purchases = Purchases.objects.filter(base_filter, date_filter)
        sales = Sales.objects.filter(base_filter, date_filter)
        commissions = Commissions.objects.filter(base_filter, date_filter)
        from core.models import StockTransfers
        transfers = StockTransfers.objects.filter(base_filter, date_filter)
        
        stocks = {} # {godown_id: {'purchase_qty', 'purchase_value', 'balance_qty'}}
        
        def ensure_godown(g_id):
            if g_id and g_id not in stocks:
                stocks[g_id] = {'purchase_qty': Decimal(0), 'purchase_value': Decimal(0), 'balance_qty': Decimal(0)}

        # 1. Process Purchases (Increases Qty and sets Value base)
        for p in purchases:
            ensure_godown(p.godown_id)
            if p.godown_id:
                qty = Decimal(str(p.qty))
                stocks[p.godown_id]['purchase_qty'] += qty
                stocks[p.godown_id]['purchase_value'] += qty * Decimal(str(p.amount))
                stocks[p.godown_id]['balance_qty'] += qty
            
        # 2. Process Sales (Decreases Qty)
        for s in sales:
            ensure_godown(s.godown_id)
            if s.godown_id:
                stocks[s.godown_id]['balance_qty'] -= Decimal(str(s.qty))

        # 3. Process Commissions (Decreases Qty)
        for c in commissions:
            ensure_godown(c.godown_id)
            if c.godown_id:
                stocks[c.godown_id]['balance_qty'] -= Decimal(str(c.qty))

        # 4. Process Stock Transfers
        for t in transfers:
            ensure_godown(t.transfer_from_id)
            ensure_godown(t.transfer_to_id)
            if t.transfer_from_id:
                stocks[t.transfer_from_id]['balance_qty'] -= Decimal(str(t.qty))
            if t.transfer_to_id:
                stocks[t.transfer_to_id]['balance_qty'] += Decimal(str(t.qty))
                # Note: For weighted average, transfers might complicate valuation if godowns have different costs.
                # Here we assume a global average cost per Godown based on its own purchases.
            
        # Calculate Value
        total_value_all = Decimal('0.0000')
        for item in stocks.values():
            if item['balance_qty'] > 0:
                avg_rate = (item['purchase_value'] / item['purchase_qty']).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP) if item['purchase_qty'] > 0 else Decimal(0)
                total_value_all += (Decimal(str(item['balance_qty'])) * avg_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
        return total_value_all

class PandLService:
    @staticmethod
    def get_financial_data(client, start_date, end_date):
        """
        Aggregates financial data for Profit & Loss statement.
        """
        # Convert dates to datetime for created_at filtering if needed
        # Assuming end_date is inclusive (end of day)
        end_datetime = datetime.datetime.combine(end_date, datetime.time.max)
        start_datetime = datetime.datetime.combine(start_date, datetime.time.min)

        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter_range = Q(date__range=[start_date, end_date])
        created_at_filter_range = Q(created_at__range=[start_datetime, end_datetime])

        # 1. Opening Stock (Value at start_date - 1 day)
        opening_stock_date = start_date - datetime.timedelta(days=1)
        opening_stock_value = StockService.calculate_stock_value(client, opening_stock_date)

        # 2. Closing Stock (Value at end_date)
        closing_stock_value = StockService.calculate_stock_value(client, end_date)

        # 3. Sales (Income)
        # Sales Model has 'date' field
        base_sales = Sales.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_sales = NSDs.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        sales_total = base_sales + nsd_sales

        # 4. Purchases (Expense)
        # Purchases Model has 'date' field
        base_purchases = Purchases.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_purchases = NSDs.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        purchases_total = base_purchases + nsd_purchases

        # 5. Expenses (Indirect Expense)
        expenses_qs = Expenses.objects.filter(is_active=True, client=client, date__range=[start_date, end_date])
        expense_details = []
        total_expense = Decimal('0.0000')
        
        # Aggregate by category
        cat_map = {}
        for exp in expenses_qs:
            cat = exp.category.upper() if exp.category else "GENERAL EXPENSE"
            if cat not in cat_map:
                cat_map[cat] = Decimal('0.0000')
            cat_map[cat] += Decimal(str(exp.amount or 0))
            
        for cat, amt in cat_map.items():
            if amt > 0:
                expense_details.append({'name': cat, 'amount': amt})
                total_expense += amt

        # 6. Commissions (Expense)
        # Commissions Model has 'date' field
        commissions_total = Commissions.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        if commissions_total > 0:
            expense_details.append({'name': 'COMMISSIONS', 'amount': commissions_total})
            total_expense += commissions_total

        # Calculations
        # Gross Income = (Sales + Closing Stock) - (Opening Stock + Purchases)
        gross_income = (sales_total + closing_stock_value) - (opening_stock_value + purchases_total)
        
        # Net Income = Gross Income - Indirect Expenses
        net_income = gross_income - total_expense

        return {
            'opening_stock': opening_stock_value,
            'closing_stock': closing_stock_value,
            'sales': sales_total,
            'purchases': purchases_total,
            'gross_income': gross_income,
            'expenses': expense_details,
            'total_expense': total_expense,
            'net_income': net_income
        }

class TrialBalanceService:
    @staticmethod
    def calculate_party_balance(entity, client, date_limit, is_customer=True):
        if is_customer:
            return calculate_customer_balance(entity, client, date_limit)
        else:
            return calculate_supplier_balance(entity, client, date_limit)

    @staticmethod
    def get_trial_balance(client, date_limit):
        accounts = []
        base_filter_active = Q(is_active=True, hold=False, client=client)
        
        # Determine Financial Year Start (Default Jan 1st of current year)
        # Ideally this should be configurable, but consistent with P&L defaults for now
        start_date = datetime.date(date_limit.year, 1, 1)
        
        # Real Accounts (Cumulative -> LTE)
        date_filter_cumulative = Q(date__lte=date_limit)
        
        # Nominal Accounts (Periodic -> Range)
        date_filter_periodic = Q(date__range=[start_date, date_limit])
        
        # 1. CASH / BANK (Assets -> Debit)
        # Commissions and Expenses don't create Cashs records, so their cash outflows
        # must be deducted here to avoid overstating Cash In Hand.
        cash_received = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')

        commissions_total = Commissions.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        expenses_total = Expenses.objects.filter(is_active=True, client=client, date__range=[start_date, date_limit]).aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')

        cash_balance = cash_received - cash_paid - commissions_total - expenses_total
        
        # Add Opening Balance Equity (C7 fix)
        total_open_credit = Customers.objects.filter(is_active=True, client=client).aggregate(s=Sum('open_credit'))['s'] or Decimal('0')
        total_open_credit += Suppliers.objects.filter(is_active=True, client=client).aggregate(s=Sum('open_credit'))['s'] or Decimal('0')
        total_open_debit = Customers.objects.filter(is_active=True, client=client).aggregate(s=Sum('open_debit'))['s'] or Decimal('0')
        total_open_debit += Suppliers.objects.filter(is_active=True, client=client).aggregate(s=Sum('open_debit'))['s'] or Decimal('0')
        
        obe_balance = total_open_debit - total_open_credit
        if obe_balance != 0:
            accounts.append({
                'code': '3000',
                'name': 'OPENING BALANCE EQUITY',
                'debit': abs(obe_balance) if obe_balance < 0 else 0,
                'credit': abs(obe_balance) if obe_balance > 0 else 0,
            })

        if cash_balance != 0:
            accounts.append({
               'code': '1001',
               'name': 'CASH IN HAND',
               'phone': '',
               'debit': abs(cash_balance) if cash_balance > 0 else 0,
               'credit': abs(cash_balance) if cash_balance < 0 else 0,
            })

        # 2. CUSTOMERS (Real)
        customers = Customers.objects.filter(is_active=True, client=client)
        for c in customers:
             bal = TrialBalanceService.calculate_party_balance(c, client, date_limit, is_customer=True)
             if bal != 0:
                 accounts.append({
                     'code': c.customerId,
                     'name': c.name,
                     'debit': bal if bal > 0 else 0,
                     'credit': abs(bal) if bal < 0 else 0
                 })

        # 3. SUPPLIERS (Real)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        for s in suppliers:
             bal = TrialBalanceService.calculate_party_balance(s, client, date_limit, is_customer=False)
             if bal != 0:
                 accounts.append({
                     'code': s.supplierId,
                     'name': s.name,
                     'debit': bal if bal > 0 else 0,
                     'credit': abs(bal) if bal < 0 else 0
                 })

        # 4. STOCK (Nominal - Opening Stock for the Period)
        # Opening Stock is stock value at Start Date - 1 Day
        opening_stock_date = start_date - datetime.timedelta(days=1)
        stock_value = StockService.calculate_stock_value(client, opening_stock_date)
        if stock_value > 0:
            accounts.append({
                'code': '52000001',
                'name': 'STOCK OPEN.BALANCE (P&L)', 
                'debit': stock_value,
                'credit': 0
            })

        # 5. SALES (Nominal - Periodic)
        base_sales = Sales.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_sales = NSDs.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        total_sales = base_sales + nsd_sales
        if total_sales > 0:
             accounts.append({
                'code': '41000001',
                'name': 'SALES A/C',
                'debit': 0,
                'credit': total_sales
            })

        # 6. PURCHASES (Nominal - Periodic)
        base_purchases = Purchases.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_purchases = NSDs.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        total_purchases = base_purchases + nsd_purchases
        if total_purchases > 0:
             accounts.append({
                'code': '51000001',
                'name': 'PURCHASE A/C',
                'debit': total_purchases,
                'credit': 0
            })
            
        # 7. EXPENSES (Nominal - Periodic)
        expense_cats = {}
        for exp in Expenses.objects.filter(is_active=True, client=client, date__range=[start_date, date_limit]):
            cat = exp.category.upper() if exp.category else "GENERAL EXPENSE"
            if cat not in expense_cats:
                expense_cats[cat] = Decimal('0.0000')
            expense_cats[cat] += Decimal(str(exp.amount or 0))

        for cat, amount in expense_cats.items():
            if amount > 0:
                accounts.append({
                    'code': '6100000X',
                    'name': cat,
                    'debit': amount,
                    'credit': 0
                })

        # 8. COMMISSIONS (Nominal - Periodic)
        if commissions_total > 0:
            accounts.append({
                'code': '62000001',
                'name': 'COMMISSIONS',
                'debit': commissions_total,
                'credit': 0
            })

        accounts.sort(key=lambda x: x['name'])
        
        total_debit = sum(a['debit'] for a in accounts)
        total_credit = sum(a['credit'] for a in accounts)
        difference = total_debit - total_credit
        
        return {
            'accounts': accounts,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'difference': difference,
            'is_balanced': difference == Decimal('0')
        }


