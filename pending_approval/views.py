from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from core.models import Collection, Cashs, CashBanks, Sales, Customers, Suppliers
from core.views import getClient, update_ledger
from cash_entry.views import getLastCashNo
from django.db.models import Sum, Count
from decimal import Decimal, InvalidOperation

@method_decorator(never_cache, name='dispatch')
class PendingApprovalView(LoginRequiredMixin, View):
    def get(self, request):
        client = getClient(request.user)
        
        date_str = request.GET.get('date')
        if not date_str:
            date_obj = timezone.localtime(timezone.now()).date()
            date_str = date_obj.strftime('%Y-%m-%d')
        else:
            try:
                date_obj = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date_obj = timezone.localtime(timezone.now()).date()
                date_str = date_obj.strftime('%Y-%m-%d')

        collections = Collection.objects.filter(
            client=client, 
            status='Pending',
            date=date_obj
        ).annotate(
            pending_total=Sum('items__collected_amount'),
            items_count=Count('items')
        ).order_by('-date')

        return render(request, 'pending_approval/pending_approval.html', {
            'collections': collections,
            'selected_date': date_str
        })

@method_decorator(never_cache, name='dispatch')
class PendingApprovalDetailView(LoginRequiredMixin, View):
    def get(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        items = list(collection.items.all())
        
        for item in items:
            item.partner_name = "Unknown"
            
            if item.transaction_type == 'Customer':
                c = Customers.objects.filter(id=item.transaction_id).first()
                if c: item.partner_name = c.name
            elif item.transaction_type == 'Supplier':
                s = Suppliers.objects.filter(id=item.transaction_id).first()
                if s: item.partner_name = s.name
            elif item.transaction_type == 'Sale':
                sale = Sales.objects.filter(sale_no=item.transaction_id, client=client).first()
                if sale and sale.customer:
                    item.partner_name = sale.customer.name
        
        cashbanks = CashBanks.objects.filter(client=client, is_active=True)
        return render(request, 'pending_approval/approval_detail.html', {
            'collection': collection,
            'items': items,
            'cashbanks': cashbanks
        })

    @transaction.atomic
    def post(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        action = request.POST.get('action')
        
        if action == 'reject':
            collection.status = 'Rejected'
            collection.is_viewed = False
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
            
            cash_bank = get_object_or_404(CashBanks.objects.select_for_update(), id=cb_id, client=client)

            items = collection.items.all()
            approved_count = 0
            total_approved_amount = Decimal('0.0000')

            # Generate cash number once before the loop and increment per item
            # to prevent duplicate cash numbers (VULN #46)
            next_cash_no = getLastCashNo(client=client)

            for item in items:
                amount_str = request.POST.get(f'amount_{item.id}')
                try:
                    amount = Decimal(str(amount_str or 0))
                except (ValueError, TypeError, InvalidOperation):
                    amount = Decimal('0.0000')
                
                if item.collected_amount != amount:
                    item.collected_amount = amount
                    item.save()
                
                if amount > 0:
                    approved_count += 1
                    total_approved_amount += amount

                    customer = None
                    supplier = None
                    
                    if item.transaction_type == 'Customer':
                        customer = Customers.objects.filter(id=item.transaction_id).first()
                    elif item.transaction_type == 'Supplier':
                        supplier = Suppliers.objects.filter(id=item.transaction_id).first()
                    elif item.transaction_type == 'Sale':
                        sale = Sales.objects.filter(sale_no=item.transaction_id, client=client).first()
                        if sale:
                            customer = sale.customer
                    
                    party = customer or supplier
                    
                    if party:
                        update_ledger(where=party, to=None, new_purchase=amount, old_purchase=0)
                        
                        Cashs.objects.create(
                            client=client,
                            cash_no=str(next_cash_no),
                            supplier=supplier,
                            customer=customer,
                            cash_bank=cash_bank,
                            date=timezone.now().date(),
                            amount=amount,
                            party_balance=party.balance,
                            transaction='Received',
                            description=f"{item.remark}" if item.remark else "",
                            hold=False,
                            is_active=True
                        )
                        # Increment for the next item
                        if str(next_cash_no).isdigit():
                            next_cash_no = str(int(next_cash_no) + 1)
                        else:
                            next_cash_no = str(next_cash_no) + '_1'

            if total_approved_amount > 0:
                cash_bank.balance = Decimal(str(cash_bank.balance)) + total_approved_amount
                cash_bank.save()

            collection.status = 'Approved'
            collection.is_viewed = False
            collection.approved_by = request.user
            collection.approval_date = timezone.now()
            collection.save()
            
            messages.success(request, f"Collection approved. {approved_count} entries posted.")
            return redirect('pendingapproval')
            
        return redirect('pendingapproval')