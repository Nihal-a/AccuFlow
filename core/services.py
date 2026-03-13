from decimal import Decimal
from django.db.models import Sum, Q
from core.models import Purchases, Sales, NSDs, Cashs, Customers, Suppliers, CashBanks, Godowns

class FinancialService:
    @staticmethod
    def calculate_supplier_balance(supplier, client, date_limit=None):
        base_filter = Q(is_active=True, hold=False, client=client, supplier=supplier)
        nsd_base = Q(is_active=True, hold=False, client=client)
        
        if date_limit:
            base_filter &= Q(date__lte=date_limit)
            nsd_base &= Q(date__lte=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sender_sum = NSDs.objects.filter(nsd_base, sender_supplier=supplier).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        receiver_sum = NSDs.objects.filter(nsd_base, receiver_supplier=supplier).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
        static_ob = supplier.open_debit - supplier.open_credit
        
        return static_ob + transaction_balance

    @staticmethod
    def calculate_customer_balance(customer, client, date_limit=None):
        base_filter = Q(is_active=True, hold=False, client=client, customer=customer)
        nsd_base = Q(is_active=True, hold=False, client=client)
        
        if date_limit:
            base_filter &= Q(date__lte=date_limit)
            nsd_base &= Q(date__lte=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sender_sum = NSDs.objects.filter(nsd_base, sender_customer=customer).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=customer).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
        static_ob = customer.open_debit - customer.open_credit
        
        return static_ob + transaction_balance

    @staticmethod
    def calculate_cashbank_balance(cashbank, client, date_limit=None):
        base_filter = Q(is_active=True, hold=False, client=client, cash_bank=cashbank)
        if date_limit:
            base_filter &= Q(date__lte=date_limit)
            
        received_sum = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        paid_sum = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        return received_sum - paid_sum

    @staticmethod
    def calculate_godown_qty(godown, client, date_limit=None):
        from core.models import Purchases, Sales, StockTransfers, Commissions
        base_filter = Q(is_active=True, hold=False, client=client)
        if date_limit:
            base_filter &= Q(date__lte=date_limit)
            
        p_qty = Purchases.objects.filter(base_filter, godown=godown).aggregate(s=Sum('qty'))['s'] or Decimal('0')
        s_qty = Sales.objects.filter(base_filter, godown=godown).aggregate(s=Sum('qty'))['s'] or Decimal('0')
        c_qty = Commissions.objects.filter(base_filter, godown=godown).aggregate(s=Sum('qty'))['s'] or Decimal('0')
        
        t_in = StockTransfers.objects.filter(base_filter, transfer_to=godown).aggregate(s=Sum('qty'))['s'] or Decimal('0')
        t_out = StockTransfers.objects.filter(base_filter, transfer_from=godown).aggregate(s=Sum('qty'))['s'] or Decimal('0')
        
        return (p_qty + t_in) - (s_qty + c_qty + t_out)

    @staticmethod
    def update_party_balance(party):
        if party.debit > 0 and party.credit > 0:
            cancel = min(party.debit, party.credit)
            party.debit -= cancel
            party.credit -= cancel
        
        party.balance = party.debit - party.credit

    @staticmethod
    def update_ledger(where, to=None, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):
        if where:
            where = type(where).objects.select_for_update().get(pk=where.pk)
            if Decimal(old_purchase) > 0: 
                where.credit -= Decimal(old_purchase)
                if where.credit < 0:
                    where.debit += abs(where.credit)
                    where.credit = 0
            if Decimal(new_purchase) > 0:
                where.credit += Decimal(new_purchase)
            FinancialService.update_party_balance(where)
            where.save()

        if to:
            to = type(to).objects.select_for_update().get(pk=to.pk)
            if Decimal(old_sale) > 0:
                to.debit -= Decimal(old_sale)
                if to.debit < 0:
                    to.credit += abs(to.debit)
                    to.debit = 0
            if Decimal(new_sale) > 0:
                to.debit += Decimal(new_sale)
            FinancialService.update_party_balance(to)
            to.save()
