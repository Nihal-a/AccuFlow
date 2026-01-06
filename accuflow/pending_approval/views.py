from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from core.models import Collection, Cashs, CashBanks, Sales
from core.views import getClient, update_ledger
from cash_entry.views import getLastCashNo
from django.db.models import Sum, Count

class PendingApprovalView(LoginRequiredMixin, View):
    def get(self, request):
        client = getClient(request.user)
        # Fetch collections pending approval with total amount
        collections = Collection.objects.filter(client=client, status='Pending').annotate(
            pending_total=Sum('items__collected_amount'),
            items_count=Count('items')
        ).order_by('-date')
        return render(request, 'pending_approval/pending_approval.html', {'collections': collections})

class PendingApprovalDetailView(LoginRequiredMixin, View):
    def get(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        items = list(collection.items.all())
        
        # Enrich items with customer info for display
        for item in items:
            if item.transaction_type == 'Sale':
                sale = Sales.objects.filter(sale_no=item.transaction_id, client=client).first()
                if sale and sale.customer:
                    item.customer_name = sale.customer.name
                    item.customer_obj = sale.customer # Pass object if needed
        
        cashbanks = CashBanks.objects.filter(client=client, is_active=True)
        return render(request, 'pending_approval/approval_detail.html', {
            'collection': collection,
            'items': items,
            'cashbanks': cashbanks
        })

    def post(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        action = request.POST.get('action')
        
        if action == 'reject':
            collection.status = 'Rejected'
            collection.approved_by = request.user
            collection.approval_date = timezone.now()
            collection.save()
            messages.info(request, "Collection rejected.")
            return redirect('pendingapproval')
        
        if action == 'approve':
            cb_id = request.POST.get('cash_bank')
            if not cb_id:
                messages.error(request, "Please select a Cash/Bank account for deposit.")
                return redirect('pending_approval_detail', id=id)
            
            cash_bank = get_object_or_404(CashBanks, id=cb_id, client=client)
            
            items = collection.items.all()
            approved_count = 0
            
            for item in items:
                # Get updated amount from Admin input
                amount_str = request.POST.get(f'amount_{item.id}')
                try:
                    amount = float(amount_str)
                except (ValueError, TypeError):
                    amount = 0
                
                # Update item amount if changed
                if item.collected_amount != amount:
                    item.collected_amount = amount
                    item.save()
                
                if amount > 0:
                    approved_count += 1
                    # Logic to find Customer
                    customer = None
                    if item.transaction_type == 'Sale':
                        sale = Sales.objects.filter(sale_no=item.transaction_id, client=client).first()
                        if sale:
                            customer = sale.customer
                    
                    if customer:
                        # 1. Update Ledger (Credit Customer)
                        # 'Received' transaction reduces customer balance (Credit side)
                        # Using pattern from CashAddView: update_ledger(where=customer, to=None, new_purchase=amount, old_purchase=0)
                        update_ledger(where=customer, to=None, new_purchase=amount, old_purchase=0)
                        
                        # 2. Create Cashs Entry
                        Cashs.objects.create(
                            client=client,
                            cash_no=getLastCashNo(client=client), # Helper function
                            supplier=None,
                            customer=customer,
                            cash_bank=cash_bank,
                            date=timezone.now().date(), # Or collection.date? Usually approval date is posting date.
                            amount=amount,
                            party_balance=customer.balance, # Updated balance
                            transaction='Received',
                            # which_type='customers', # Computed property
                            description=customer.name,
                            hold=False,
                            is_active=True
                        )

            collection.status = 'Approved'
            collection.approved_by = request.user
            collection.approval_date = timezone.now()
            collection.save()
            
            messages.success(request, f"Collection approved. {approved_count} entries posted.")
            return redirect('pendingapproval')
            
        return redirect('pendingapproval')