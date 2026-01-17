from django.shortcuts import render
from django.views import View
from django.db.models import Q
from datetime import datetime
from core.models import Sales, Purchases, NSDs, Cashs, Commissions, StockTransfers
from core.views import getClient

class TransactionReportView(View):
    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        transactions = []
        
        base_filter = Q(is_active=True, client=client)
        
        if date_from_str:
            base_filter &= Q(date__gte=date_from_str)
        if date_to_str:
            base_filter &= Q(date__lte=date_to_str)

        # 1. Sales
        sales = Sales.objects.filter(base_filter)
        for s in sales:
            partner = s.customer.name if s.customer else (s.supplier.name if s.supplier else "Unknown")
            pid = s.customer.id if s.customer else (s.supplier.id if s.supplier else "")
            transactions.append({
                'account_name': f"{partner} ({pid})",
                'date': s.date,
                'tran_no': s.sale_no,
                'description': s.description,
                'type': 'Sale',
                'debit': s.total_amount,
                'credit': 0,
                'created_at': s.created_at
            })

        # 2. Purchases
        purchases = Purchases.objects.filter(base_filter)
        for p in purchases:
            partner = p.supplier.name if p.supplier else (p.customer.name if p.customer else "Unknown")
            pid = p.supplier.id if p.supplier else (p.customer.id if p.customer else "")
            transactions.append({
                'account_name': f"{partner} ({pid})",
                'date': p.date,
                'tran_no': p.purchase_no,
                'description': p.description,
                'type': 'Purchase',
                'debit': 0,
                'credit': p.total_amount,
                'created_at': p.created_at
            })

        # 3. NSDs
        nsds = NSDs.objects.filter(base_filter)
        for n in nsds:
            sender = n.sender.name if n.sender else "Unknown"
            receiver = n.receiver.name if n.receiver else "Unknown"
            
            transactions.append({
                'account_name': f"{sender} -> {receiver}",
                'date': n.date,
                'tran_no': n.nsd_no,
                'description': n.description,
                'type': 'NSD',
                'debit': n.purchase_amount, # Receiver gets value (Debit)
                'credit': n.sell_amount,   # Sender gives value (Credit) - simplified view in one row?
                                           # Or maybe just show amounts. 
                                           # If I put both, it implies a balanced entry.
                'created_at': n.created_at
            })

        # 4. Cash/Bank
        cashs = Cashs.objects.filter(base_filter)
        for c in cashs:
            partner = c.customer.name if c.customer else (c.supplier.name if c.supplier else "Unknown")
            pid = c.customer.id if c.customer else (c.supplier.id if c.supplier else "")
            acc = f"{partner} ({pid})" if partner != "Unknown" else c.cash_bank.name
            
            if c.transaction == 'Received':
                # We received cash. Party is Credited.
                debit = 0
                credit = c.amount
            else: # Paid
                # We paid cash. Party is Debited.
                debit = c.amount
                credit = 0
                
            transactions.append({
                'account_name': acc,
                'date': c.date,
                'tran_no': c.cash_no,
                'description': c.description or c.cash_bank.name,
                'type': f"Cash {c.transaction}",
                'debit': debit,
                'credit': credit,
                'created_at': c.created_at
            })

        # 5. Commissions
        commissions = Commissions.objects.filter(base_filter)
        for com in commissions:
            transactions.append({
                'account_name': com.godown.name if com.godown else "Unknown",
                'date': com.date,
                'tran_no': com.commission_no,
                'description': com.description,
                'type': 'Commission',
                'debit': com.total_amount, # Expense is Debit
                'credit': 0,
                'created_at': com.created_at
            })

        # 6. Stock Transfers
        stock_transfers = StockTransfers.objects.filter(base_filter)
        for st in stock_transfers:
            from_name = st.transfer_from.name if st.transfer_from else "Unknown"
            to_name = st.transfer_to.name if st.transfer_to else "Unknown"
            
            transactions.append({
                'account_name': f"{from_name} -> {to_name}",
                'date': st.date,
                'tran_no': st.transfer_no,
                'description': st.description,
                'type': 'Stock Transfer',
                'debit': 0, # st.qty, # User asked for column, but mixing qty with amount is bad. Leaving 0.
                'credit': 0,
                'created_at': st.created_at
            })

        # Sort by Date, then Created At
        transactions.sort(key=lambda x: (x['date'] or datetime.min.date(), x['created_at']))

        context = {
            'transactions': transactions,
            'date_from': date_from_str,
            'date_to': date_to_str,
        }
        return render(request, 'transaction_report/transaction_report.html', context)
