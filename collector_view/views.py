from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Collectors, Collection, Sales, CollectionItem, Purchases, NSDs, Customers, Suppliers
from django.utils.decorators import method_decorator
import datetime
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from core.views import calculate_customer_balance, calculate_supplier_balance

class CollectorCollectionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/collections.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_collector

    def get(self, request):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            
            date_str = request.GET.get('date')
            
            if not date_str:
                date_obj = datetime.date.today()
                date_str = date_obj.strftime('%Y-%m-%d')
            else:
                 try:
                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                 except ValueError:
                    date_obj = datetime.date.today()
                    date_str = date_obj.strftime('%Y-%m-%d')

            collections = Collection.objects.filter(collector=collector, date=date_obj).order_by('-date')

        except Collectors.DoesNotExist:
            collector = None
            collections = []
            date_str = None

        context = {
            'collections': collections,
            'collector': collector,
            'is_collector_view': True,
            'selected_date': date_str 
        }
        return render(request, self.template_name, context)

class CollectorCollectionDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/collection_detail.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_collector

    def get(self, request, id):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collection = get_object_or_404(Collection, id=id, collector=collector)
        except Collectors.DoesNotExist:
            return render(request, '404.html', status=404)

        items = collection.items.all()
        
        for item in items:
            item.customer_name = "-"
            item.customer_phone = "-"
            
            if item.transaction_type == 'Customer':
                c = Customers.objects.filter(id=item.transaction_id).first()
                if c:
                     item.customer_name = c.name
                     item.customer_phone = c.phone
                     item.customer_wa = c.wa if hasattr(c, 'wa') else '' 
                     item.customer_cc = c.country_code if hasattr(c, 'country_code') else ''
                     item.customer_balance = c.balance
            elif item.transaction_type == 'Supplier':
                s = Suppliers.objects.filter(id=item.transaction_id).first()
                if s: 
                     item.customer_name = s.name
                     item.customer_phone = s.phone
                     item.customer_wa = s.wa if hasattr(s, 'wa') else ''
                     item.customer_cc = s.country_code if hasattr(s, 'country_code') else ''
                     item.customer_balance = s.balance
            elif item.transaction_type == 'Sale':
                sale = Sales.objects.filter(sale_no=item.transaction_id, client=collector.client).first()
                if sale and sale.customer:
                    item.customer_name = sale.customer.name
                    item.customer_phone = sale.customer.phone
                    item.customer_wa = sale.customer.wa
                    item.customer_cc = sale.customer.country_code
                    item.customer_balance = sale.customer.balance
        
        read_only = collection.status not in ['New', 'Rejected']
        context = {
            'collection': collection,
            'items': items,
            'read_only': read_only,
        }
        return render(request, self.template_name, context)

    def post(self, request, id):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collection = get_object_or_404(Collection, id=id, collector=collector)
        except Collectors.DoesNotExist:
            return render(request, '404.html', status=404)
            
        if collection.status not in ['New', 'Rejected']:
             messages.error(request, "This collection cannot be edited.")
             return redirect('my_collection_detail', id=id)

        items = list(collection.items.all())
        filled_items = []
        
        for item in items:
            amount_str = request.POST.get(f'collected_amount_{item.id}')
            amount = Decimal('0.0000')
            if amount_str:
                try:
                    amount = Decimal(str(amount_str))
                except (ValueError, InvalidOperation):
                    amount = Decimal('0.0000')
            
            item.collected_amount = amount
            item.remark = request.POST.get(f'remark_{item.id}', '')
            item.save()
            
            if amount > 0:
                filled_items.append(item)
        
        if not filled_items:
            messages.warning(request, "No collected amounts entered.")
            return redirect('my_collection_detail', id=id)
            
        # If specifically Rejected, we reuse the SAME collection ID for re-approval
        if collection.status == 'Rejected':
            collection.status = 'Pending'
            collection.save()
            messages.success(request, "Collection re-submitted for approval.")
            return redirect('my_collection_detail', id=collection.id)

        if len(filled_items) < len(items):
            new_collection = Collection.objects.create(
                collector=collector,
                client=collection.client,
                date=collection.date,
                status='Pending',
            )
            
            for item in filled_items:
                item.collection = new_collection
                item.save()
            
            messages.success(request, f"Submitted {len(filled_items)} items for approval. Remaining items are kept here.")
            return redirect('my_collection_detail', id=collection.id)
        
        else:
            collection.status = 'Pending'
            collection.save()
            messages.success(request, "Collection submitted for approval.")
            return redirect('my_collection_detail', id=collection.id)

class CollectorAddItemsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/add_items.html'
    
    def test_func(self):
        if not (self.request.user.is_authenticated and self.request.user.is_collector):
            return False
        try:
             c = Collectors.objects.get(user=self.request.user, is_active=True)
             return c.can_collect_directly
        except:
             return False

    def get(self, request, id):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collection = get_object_or_404(Collection, id=id, collector=collector)
        except Collectors.DoesNotExist:
             return redirect('my_collections')
             
        client = collector.client
        existing_keys = [f"{item.transaction_type}_{item.transaction_id}" for item in collection.items.all()]
        
        receivables = []
        
        customers = Customers.objects.filter(client=client, is_active=True)
        for c in customers:
             bal = calculate_customer_balance(c, client)
             if bal > 0:
                 key = f"Customer_{c.id}"
                 if key not in existing_keys:
                    receivables.append({
                        'id': key,
                        'type': 'Customer',
                        'name': c.name,
                        'phone': c.phone,
                        'balance': bal
                    })

        suppliers = Suppliers.objects.filter(client=client, is_active=True)
        for s in suppliers:
             bal = calculate_supplier_balance(s, client)
             if bal > 0:
                 key = f"Supplier_{s.id}"
                 if key not in existing_keys:
                    receivables.append({
                        'id': key,
                        'type': 'Supplier',
                        'name': s.name,
                        'phone': s.phone,
                        'balance': bal
                    })
        
        context = {
            'collection': collection,
            'receivables': receivables
        }
        return render(request, self.template_name, context)

    def post(self, request, id):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collection = get_object_or_404(Collection, id=id, collector=collector)
        except Collectors.DoesNotExist:
             return redirect('my_collections')
             
        selected_ids = request.POST.getlist('selected_receivables')
        
        if selected_ids:
            # If collection is Approved, start a fresh one for the same date
            if collection.status == 'Approved':
                 collection = Collection.objects.create(
                    collector=collector,
                    client=collection.client,
                    date=collection.date,
                    status='New',
                    total_amount=Decimal('0.0000')
                )
            # If it was Pending, reset to New so it can be edited
            elif collection.status == 'Pending':
                 collection.status = 'New'
                 collection.save()

            for item_key in selected_ids:
                type_str, id_str = item_key.split('_')
                # Check uniqueness again to be safe
                if not CollectionItem.objects.filter(collection=collection, transaction_type=type_str, transaction_id=id_str).exists():
                     # Determine amount (current balance)
                    amount = Decimal('0.0000')
                    if type_str == 'Customer':
                        c = Customers.objects.filter(id=id_str).first()
                        if c: amount = calculate_customer_balance(c, collection.client)
                    elif type_str == 'Supplier':
                        s = Suppliers.objects.filter(id=id_str).first()
                        if s: amount = calculate_supplier_balance(s, collection.client)
                    
                    if amount > 0:
                        CollectionItem.objects.create(
                            collection=collection,
                            transaction_id=id_str,
                            transaction_type=type_str,
                            amount=amount,
                            collected_amount=Decimal('0.0000'), # Initially 0, collector enters it
                            is_credit=False
                        )
            
            messages.success(request, f"{len(selected_ids)} partners added to collection.")
            
        return redirect('my_collection_detail', id=collection.id)
