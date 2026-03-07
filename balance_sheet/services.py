from decimal import Decimal
from django.db.models import Sum, Q
from core.models import Customers, Suppliers, Cashs, Commissions
from profit_loss.services import PandLService, StockService, TrialBalanceService
import datetime

class BalanceSheetService:
    @staticmethod
    def get_balance_sheet(client, date_to):
        """
        Generates Balance Sheet data as of date_to using a flat structure (Debit/Credit).
        """
        accounts = []
        
        # --- ASSETS SECTION ---
        accounts.append({'code': '1100', 'name': 'FIXED ASSETS **', 'is_header': True})
        # Placeholder for Fixed Assets if any
        
        accounts.append({'code': '1200', 'name': 'CURRENT ASSETS **', 'is_header': True})
        
        # 1. Cash & Bank
        base_filter_active = Q(is_active=True, client=client)
        date_filter_cumulative = Q(date__lte=date_to)
        
        cash_received = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter_active, date_filter_cumulative, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        commissions_total_cash = Commissions.objects.filter(base_filter_active, date_filter_cumulative).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        cash_balance = cash_received - cash_paid - commissions_total_cash
        
        accounts.append({
            'code': '1201', 'name': 'CASH BOOK', 
            'debit': cash_balance if cash_balance >= 0 else 0, 
            'credit': abs(cash_balance) if cash_balance < 0 else 0 
        })

        # 2. Customers
        trade_debtors_total = Decimal('0.0000')
        advances_from_customers_total = Decimal('0.0000')
        
        customers = Customers.objects.filter(base_filter_active)
        for c in customers:
            bal = TrialBalanceService.calculate_party_balance(c, client, date_to, is_customer=True)
            if bal > 0:
                trade_debtors_total += bal
            elif bal < 0:
                advances_from_customers_total += abs(bal)

        accounts.append({
            'code': '1205', 'name': 'CUSTOMERS CONTROL A/C', 
            'debit': trade_debtors_total, 
            'credit': 0 
        })
        
        # 3. Suppliers (Advances)
        trade_creditors_total = Decimal('0.0000')
        advances_to_suppliers_total = Decimal('0.0000')
        
        suppliers = Suppliers.objects.filter(base_filter_active)
        for s in suppliers:
            bal = TrialBalanceService.calculate_party_balance(s, client, date_to, is_customer=False)
            if bal < 0: # Credit Balance -> Liability
                trade_creditors_total += abs(bal)
            elif bal > 0: # Debit Balance -> Asset
                advances_to_suppliers_total += bal

        if advances_to_suppliers_total > 0:
            accounts.append({
                'code': '1210', 'name': 'ADVANCES TO SUPPLIERS', 
                'debit': advances_to_suppliers_total, 
                'credit': 0
            })

        # 4. Stock
        closing_stock = StockService.calculate_stock_value(client, date_to)
        accounts.append({
            'code': '1250', 'name': 'STOCK VALUE', 
            'debit': closing_stock, 
            'credit': 0,
            'highlight': 'orange' 
        })

        # --- LIABILITIES SECTION ---
        accounts.append({'code': '2100', 'name': 'LIABILITIES **', 'is_header': True})
        accounts.append({'code': '2200', 'name': 'CURRENT LIABILITIES **', 'is_header': True})
        
        accounts.append({
            'code': '2205', 'name': 'SUPPLIER CONTROL A/C', 
            'debit': 0, 
            'credit': trade_creditors_total 
        })

        if advances_from_customers_total > 0:
             accounts.append({
                'code': '2210', 'name': 'ADVANCES FROM CUSTOMERS', 
                'debit': 0, 
                'credit': advances_from_customers_total
            })

        # --- EQUITY ---
        # Net Income
        pnl_start_date = datetime.date(2000, 1, 1)
        pnl_data = PandLService.get_financial_data(client, pnl_start_date, date_to)
        net_income = pnl_data['net_income']
        
        accounts.append({
            'code': '3900', 'name': 'PROFIT & LOSS ACCOUNT', 
            'debit': abs(net_income) if net_income < 0 else 0, # Loss is Debit
            'credit': net_income if net_income >= 0 else 0, # Profit is Credit
            'highlight': 'green'
        })

        # TOTALS
        total_debit = sum(a.get('debit', 0) for a in accounts)
        total_credit = sum(a.get('credit', 0) for a in accounts)
        difference = total_debit - total_credit

        return {
            'accounts': accounts,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'difference': difference,
            'is_balanced': abs(difference) < Decimal('0.01'),
        }
