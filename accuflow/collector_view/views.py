from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Collectors, Collection, Sales, CollectionItem, Purchases, NSDs
from django.utils.decorators import method_decorator
import datetime
from django.contrib.auth.decorators import login_required

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class CollectorCollectionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/collections.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_collector

    def get(self, request):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collections = Collection.objects.filter(collector=collector).order_by('-date')
        except Collectors.DoesNotExist:
            collector = None
            collections = []

        context = {
            'collections': collections,
            'collector': collector,
            'is_collector_view': True 
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
            
            if item.transaction_type == 'Sale':
                sale = Sales.objects.filter(sale_no=item.transaction_id, client=collector.client).first()
                if sale and sale.customer:
                    item.customer_name = sale.customer.name
                    item.customer_phone = sale.customer.phone
                    item.customer_wa = sale.customer.wa
                    item.customer_cc = sale.customer.country_code
                    item.customer_balance = sale.customer.balance
        
        read_only = collection.status != 'New'
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
            
        if collection.status != 'New':
             messages.error(request, "This collection cannot be edited.")
             return redirect('my_collection_detail', id=id)

        items = list(collection.items.all())
        filled_items = []
        
        for item in items:
            amount_str = request.POST.get(f'collected_amount_{item.id}')
            amount = 0
            if amount_str:
                try:
                    amount = float(amount_str)
                except ValueError:
                    amount = 0
            
            item.collected_amount = amount
            item.save()
            
            if amount > 0:
                filled_items.append(item)
        
        if not filled_items:
            messages.warning(request, "No collected amounts entered.")
            return redirect('my_collection_detail', id=id)
            
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

class DirectCollectionCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/create_direct.html'
    
    def test_func(self):
        if not (self.request.user.is_authenticated and self.request.user.is_collector):
            return False
        try:
             c = Collectors.objects.get(user=self.request.user, is_active=True)
             return c.can_collect_directly
        except:
             return False

    def get(self, request):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
        except Collectors.DoesNotExist:
             return redirect('my_collections')

        client = collector.client
        transactions = []
        
        sales = Sales.objects.filter(client=client, is_active=True).select_related('customer')
        for s in sales:
             if s.customer and s.customer.balance > 0:
                 transactions.append({
                     'id': f"SALE_{s.id}",
                     'transaction_id': s.sale_no,
                     'label': f"SALE: {s.customer.name} - {s.sale_no}",
                     'amount': s.total_amount, 
                     'customer_name': s.customer.name,
                     'date': s.date,
                     'balance': s.customer.balance,
                     'type': 'SALE'
                 })
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        context = {
            'transactions': transactions, 
            'today_date': datetime.date.today().strftime('%Y-%m-%d')
        }
        return render(request, self.template_name, context)

    def post(self, request):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
        except Collectors.DoesNotExist:
             return redirect('my_collections')
             
        date_str = request.POST.get('date')
        selected_ids = request.POST.getlist('selected_transactions') 
        
        if not selected_ids:
             messages.error(request, "Please select at least one transaction.")
             return redirect('create_direct_collection')
             
        try:
            if date_str:
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date_obj = datetime.date.today()
            
            collection = Collection.objects.create(
                collector=collector,
                date=date_obj,
                client=collector.client,
                status='New',
                total_amount=0
            )
            
            total_amt = 0
            for item_str in selected_ids:
                type_str, id_str = item_str.split('_')
                db_id = int(id_str)
                
                if type_str == 'SALE':
                    obj = Sales.objects.get(id=db_id)
                    
                    CollectionItem.objects.create(
                        collection=collection,
                        transaction_id=obj.sale_no,
                        transaction_type='Sale',
                        amount=obj.total_amount,
                        is_credit=False
                    )
                    total_amt += obj.total_amount
            
            collection.total_amount = total_amt
            collection.save()
            
            messages.success(request, "Direct collection created. Please enter collected amounts.")
            return redirect('my_collection_detail', id=collection.id)
            
        except Exception as e:
            messages.error(request, f"Error creating collection: {e}")
            return redirect('create_direct_collection')
