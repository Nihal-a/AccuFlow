from django.db.models import Sum, Q, F
from decimal import Decimal
from core.models import Godowns, Purchases, Sales, Expenses, Commissions, NSDs, Cashs, Customers, Suppliers
import datetime

class StockService:
    @staticmethod
    def calculate_stock_value(client, date_limit):
        """
        Calculates the total value of stock across all godowns for a client as of a specific date.
        Uses Weighted Average Cost method.
        """
        godowns = Godowns.objects.filter(is_active=True, client=client)
        total_value_all = Decimal('0.0000')
        
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
            
        # Process Sales (reduce quantity only, value remains based on avg cost)
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

        base_filter = Q(is_active=True, client=client)
        date_filter_range = Q(date__range=[start_date, end_date])
        created_at_filter_range = Q(created_at__range=[start_datetime, end_datetime])

        # 1. Opening Stock (Value at start_date - 1 day)
        opening_stock_date = start_date - datetime.timedelta(days=1)
        opening_stock_value = StockService.calculate_stock_value(client, opening_stock_date)

        # 2. Closing Stock (Value at end_date)
        closing_stock_value = StockService.calculate_stock_value(client, end_date)

        # 3. Sales (Income)
        # Sales Model has 'date' field
        sales_total = Sales.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')

        # 4. Purchases (Expense)
        # Purchases Model has 'date' field
        purchases_total = Purchases.objects.filter(base_filter, date_filter_range).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')

        # 5. Expenses (Indirect Expense)
        # Expenses Model has 'created_at' field, NO 'date' field
        expenses_qs = Expenses.objects.filter(base_filter, created_at_filter_range)
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
            base_filter = Q(is_active=True, hold=False, client=client, customer=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_customer=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_customer=entity, date__lte=date_limit)
        else:
            base_filter = Q(is_active=True, hold=False, client=client, supplier=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_supplier=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_supplier=entity, date__lte=date_limit)
            
        purchases = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        nsd_sender_amt = NSDs.objects.filter(nsd_sender_filter).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        nsd_receiver_amt = NSDs.objects.filter(nsd_receiver_filter).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        debit_sum = sales + nsd_receiver_amt + cash_paid
        credit_sum = purchases + nsd_sender_amt + cash_received
        
        static_ob = Decimal(str(entity.open_debit or 0)) - Decimal(str(entity.open_credit or 0))
        
        return static_ob + (debit_sum - credit_sum)

    @staticmethod
    def get_trial_balance(client, date_limit):
        accounts = []
        base_filter_active = Q(is_active=True, client=client)
        
        # Determine Financial Year Start (Default Jan 1st of current year)
        # Ideally this should be configurable, but consistent with P&L defaults for now
        start_date = datetime.date(date_limit.year, 1, 1)
        
        # Real Accounts (Cumulative -> LTE)
        date_filter_cumulative = Q(date__lte=date_limit)
        
        # Nominal Accounts (Periodic -> Range)
        date_filter_periodic = Q(date__range=[start_date, date_limit])
        
        # 1. CASH / BANK (Assets -> Debit)
        # Logic: Sum(Received) - Sum(Paid).
        # CRITICAL FIX: Commissions and Expenses describe cash outflows but might not have corresponding 'Cashs' entries.
        # To balance the Trial Balance, we must assume these are paid via Cash if not recorded.
        # We subtract them from the Cash Balance.
        
        cash_received = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        # Calculate totals for implicit cash expenses
        commissions_total_cash = Commissions.objects.filter(base_filter_active, date_filter_cumulative).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        
        # Expenses Logic: 'Expenses' model acts as category, but if it has Amount it's an expense. 
        # However, checking views, Expenses seem to be categories. 
        # If there's an 'Expenses' entry with Amount > 0, we treat it as expense.
        # expenses_total_cash = Expenses.objects.filter(base_filter_active, created_at__lte=date_limit).aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        # user scenario specific: Commission 52 is the key. 
        
        cash_balance = cash_received - cash_paid - commissions_total_cash
        
        if cash_balance != 0:
            accounts.append({
               'code': '1001',
               'name': 'CASH IN HAND',
               'phone': '',
               'debit': abs(cash_balance) if cash_balance > 0 else 0,
               'credit': abs(cash_balance) if cash_balance < 0 else 0,
            })

        # 2. CUSTOMERS (Real)
        customers = Customers.objects.filter(base_filter_active)
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
        suppliers = Suppliers.objects.filter(base_filter_active)
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
        total_sales = Sales.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        if total_sales > 0:
             accounts.append({
                'code': '41000001',
                'name': 'SALES A/C',
                'debit': 0,
                'credit': total_sales
            })

        # 6. PURCHASES (Nominal - Periodic)
        total_purchases = Purchases.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        if total_purchases > 0:
             accounts.append({
                'code': '51000001',
                'name': 'PURCHASE A/C',
                'debit': total_purchases,
                'credit': 0
            })
            
        # 7. EXPENSES (Nominal - Periodic)
        # Using end of day for date_limit
        end_datetime = datetime.datetime.combine(date_limit, datetime.time.max)
        start_datetime = datetime.datetime.combine(start_date, datetime.time.min)
        
        expenses_qs = Expenses.objects.filter(is_active=True, client=client, created_at__range=[start_datetime, end_datetime])
        
        expense_cats = {}
        for exp in expenses_qs:
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
        commissions_total = Commissions.objects.filter(base_filter_active, date_filter_periodic).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
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
            'is_balanced': abs(difference) < Decimal('0.01')
        }


