import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from core.models import Collectors, Sales, Purchases, NSDs, Collection, CollectionItem
from core.views import getClient
from django.contrib import messages
from django.urls import reverse

class AddCollectionView(View):
    template_name = 'view_collections/add_collection.html'

    def get(self, request, id=None):
        client = getClient(request.user)
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        instance = None
        selected_transaction_ids = []
        if id:
            instance = get_object_or_404(Collection, id=id, client=client)
            collector_id = instance.collector.id
            date_str = instance.date.strftime('%Y-%m-%d')
            selected_transaction_ids = list(instance.items.values_list('transaction_id', flat=True))
        else:
            collector_id = request.GET.get('collector')
            date_str = request.GET.get('date')
        
        transactions = []
        selected_collector = None
        
        if collector_id:
            selected_collector = get_object_or_404(Collectors, id=collector_id)
            
            # Get set of already assigned transaction IDs for this client
            used_items_query = CollectionItem.objects.filter(collection__client=client)
            if instance:
                used_items_query = used_items_query.exclude(collection=instance)
            used_transaction_ids = set(used_items_query.values_list('transaction_id', flat=True))
            
            sales = Sales.objects.filter(client=client, is_active=True)
            for s in sales:
                if s.sale_no in used_transaction_ids:
                    continue
                t_id = f"SALE_{s.id}"
                transactions.append({
                    'id': t_id,
                    'transaction_id': s.sale_no,
                    'type': 'Sale',
                    'from': s.godown.name if s.godown else 'N/A',
                    'to': s.customer.name if s.customer else 'N/A',
                    'credit': 0,
                    'debit': s.total_amount,
                    'amount': s.total_amount,
                    'is_selected': False,
                    'obj': s
                })
                
            purchases = Purchases.objects.filter(client=client, is_active=True)
            for p in purchases:
                if p.purchase_no in used_transaction_ids:
                    continue
                t_id = f"PURCHASE_{p.id}"
                transactions.append({
                    'id': t_id,
                    'transaction_id': p.purchase_no,
                    'type': 'Purchase',
                    'from': p.supplier.name if p.supplier else 'N/A',
                    'to': p.godown.name if p.godown else 'N/A',
                    'credit': p.total_amount,
                    'debit': 0,
                    'amount': p.total_amount,
                    'is_selected': False,
                    'obj': p
                })
                
            nsds = NSDs.objects.filter(client=client, is_active=True)
            for n in nsds:
                if n.nsd_no in used_transaction_ids:
                    continue
                sender = n.sender_customer.name if n.sender_customer else (n.sender_supplier.name if n.sender_supplier else 'N/A')
                receiver = n.receiver_customer.name if n.receiver_customer else (n.receiver_supplier.name if n.receiver_supplier else 'N/A')
                t_id = f"NSD_{n.id}"
                transactions.append({
                    'id': t_id,
                    'transaction_id': n.nsd_no,
                    'type': 'NSD',
                    'from': sender,
                    'to': receiver,
                    'credit': n.sell_amount,
                    'debit': n.purchase_amount,
                    'amount': n.sell_amount, 
                    'is_selected': False,
                    'obj': n
                })
                
            if instance:
                existing_txn_ids = set(instance.items.values_list('transaction_id', flat=True))
                for t in transactions:
                    if t['transaction_id'] in existing_txn_ids:
                        t['is_selected'] = True

        context = {
            'collectors': collectors,
            'transactions': transactions,
            'selected_collector': selected_collector,
            'selected_date': date_str,
            'instance': instance,
        }
        return render(request, self.template_name, context)

    def post(self, request, id=None):
        client = getClient(request.user)
        collector_id = request.POST.get('collector')
        date_str = request.POST.get('date')
        selected_ids = request.POST.getlist('selected_transactions')
        
        if not collector_id or not date_str or not selected_ids:
            messages.error(request, "Please select collector, date and at least one transaction.")
            return redirect('add_collection')

        try:
            collector = get_object_or_404(Collectors, id=collector_id)
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if id:
                collection = get_object_or_404(Collection, id=id, client=client)
                collection.collector = collector
                collection.date = date_obj
                collection.save()
                collection.items.all().delete()
                action_msg = "updated"
            else:
                collection = Collection.objects.create(
                    collector=collector,
                    date=date_obj,
                    client=client,
                    total_amount=0
                )
                action_msg = "saved"
            
            total_amt = 0
            
            for item_str in selected_ids:
                type_str, id_str = item_str.split('_')
                db_id = int(id_str)
                
                if type_str == 'SALE':
                    obj = Sales.objects.get(id=db_id)
                    amt = obj.total_amount
                    is_credit = False
                    trans_id = obj.sale_no
                    trans_type = 'Sale'
                elif type_str == 'PURCHASE':
                    obj = Purchases.objects.get(id=db_id)
                    amt = obj.total_amount
                    is_credit = True
                    trans_type = 'Purchase'
                    trans_id = obj.purchase_no
                elif type_str == 'NSD':
                    obj = NSDs.objects.get(id=db_id)
                    amt = obj.sell_amount
                    is_credit = True
                    trans_type = 'NSD'
                    trans_id = obj.nsd_no
                
                CollectionItem.objects.create(
                    collection=collection,
                    transaction_id=trans_id,
                    transaction_type=trans_type,
                    amount=amt,
                    is_credit=is_credit
                )
                total_amt += amt
            
            collection.total_amount = total_amt
            collection.save()
            
            messages.success(request, f"Collection {action_msg} successfully.")
            return redirect('collection_list')
            
        except Exception as e:
            messages.error(request, f"Error saving collection: {str(e)}")
            return redirect('add_collection')

class CollectionListView(View):
    def get(self, request):
        client = getClient(request.user)
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        collector_id = request.GET.get('collector')
        date_str = request.GET.get('date')
        
        collections = Collection.objects.filter(client=client).order_by('-date')
        
        selected_collector = None
        if collector_id:
            collections = collections.filter(collector_id=collector_id)
            selected_collector = get_object_or_404(Collectors, id=collector_id)
            
        if date_str:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            collections = collections.filter(date=date_obj)
            
        context = {
            'collectors': collectors,
            'collections': collections,
            'selected_collector': selected_collector,
            'selected_date': date_str,
        }
        return render(request, 'view_collections/collection_list.html', context)

class CollectionDetailView(View):
    def get(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        items = collection.items.all()
        
        context = {
            'collection': collection,
            'items': items,
        }
        return render(request, 'view_collections/collection_detail.html', context)

def delete_collection(request, id):
    client = getClient(request.user)
    collection = get_object_or_404(Collection, id=id, client=client)
    collection.delete()
    messages.success(request, "Collection deleted successfully.")
    return redirect('collection_list')