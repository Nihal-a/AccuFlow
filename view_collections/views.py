import datetime
import logging
from django.db.models import Sum
import decimal
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from core.models import Collectors, Sales, Purchases, NSDs, Collection, CollectionItem, Customers, Suppliers
from core.views import getClient, calculate_customer_balance, calculate_supplier_balance
from core.authorization import get_object_for_user
from django.contrib import messages
from django.urls import reverse

logger = logging.getLogger(__name__)

class AddCollectionView(View):
    template_name = 'view_collections/add_collection.html'

    def get(self, request, id=None):
        client = getClient(request.user)
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        instance = None
        receivables = []
        
        collector_id = request.GET.get('collector')
        date_str = request.GET.get('date')
        

        if id:
            instance = get_object_or_404(Collection, id=id, client=client)
        

        elif collector_id and date_str:
            try:
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                instance = Collection.objects.filter(
                    client=client, 
                    collector_id=collector_id, 
                    date=date_obj, 
                    status__in=['New', 'Pending']
                ).first()
            except ValueError:
                pass


        if instance:
            collector_id = instance.collector.id
            date_str = instance.date.strftime('%Y-%m-%d')
        
        selected_collector = None
        
        if collector_id:
            # Authorization: Ensure collector belongs to user's client
            selected_collector = get_object_for_user(Collectors, request.user, id=collector_id)
            

            customers = Customers.objects.filter(client=client, is_active=True)
            for c in customers:
                bal = calculate_customer_balance(c, client)
                if bal > 0:
                    receivables.append({
                        'id': f"Customer_{c.id}",
                        'type': 'Customer',
                        'obj_id': c.id,
                        'name': c.name,
                        'phone': c.phone,
                        'balance': bal,
                        'collected_amount': Decimal('0.0000'),
                        'is_selected': False
                    })


            suppliers = Suppliers.objects.filter(client=client, is_active=True)
            for s in suppliers:
                 bal = calculate_supplier_balance(s, client)
                 if bal > 0:
                     receivables.append({
                        'id': f"Supplier_{s.id}",
                        'type': 'Supplier',
                        'obj_id': s.id,
                        'name': s.name,
                        'phone': s.phone,
                        'balance': bal,
                        'collected_amount': Decimal('0.0000'),
                        'is_selected': False
                    })
            
            if instance:
                existing_items = {f"{item.transaction_type}_{item.transaction_id}": item.amount for item in instance.items.all()}
                

                for r in receivables:
                    key = f"{r['type']}_{r['obj_id']}"
                    if key in existing_items:
                        r['collected_amount'] = existing_items[key]
                        r['is_selected'] = True
                        del existing_items[key]
                

                for key, amount in existing_items.items():
                    type_str, id_str = key.split('_')
                    if type_str == 'Customer':
                        c = Customers.objects.get(id=id_str)
                        receivables.insert(0, {
                            'id': key,
                            'type': 'Customer',
                            'obj_id': c.id,
                            'name': c.name,
                            'phone': c.phone,
                            'balance': calculate_customer_balance(c, client),
                            'collected_amount': amount,
                            'is_selected': True
                        })
                    elif type_str == 'Supplier':
                        s = Suppliers.objects.get(id=id_str)
                        receivables.insert(0, {
                            'id': key,
                            'type': 'Supplier',
                            'obj_id': s.id,
                            'name': s.name,
                            'phone': s.phone,
                            'balance': calculate_supplier_balance(s, client),
                            'collected_amount': amount,
                            'is_selected': True
                        })

        context = {
            'collectors': collectors,
            'receivables': receivables,
            'selected_collector': selected_collector,
            'selected_date': date_str,
            'instance': instance,
        }
        return render(request, self.template_name, context)

    def post(self, request, id=None):
        client = getClient(request.user)
        collector_id = request.POST.get('collector')
        date_str = request.POST.get('date')
        
        selected_ids = request.POST.getlist('selected_receivables')
        
        if not collector_id or not date_str:
            messages.error(request, "Please select collector and date.")
            return redirect('add_collection')
        
        if not selected_ids:
             messages.error(request, "Please select at least one partner and enter amount.")
             return redirect('add_collection')

        try:
            # Authorization: Ensure collector belongs to user's client
            collector = get_object_for_user(Collectors, request.user, id=collector_id)
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            
            collection = None
            if id:
                collection = get_object_or_404(Collection, id=id, client=client)
            else:

                 collection = Collection.objects.filter(
                     client=client, 
                     collector=collector, 
                     date=date_obj,
                     status__in=['New', 'Pending']
                 ).first()

            if collection:
                collection.collector = collector
                collection.date = date_obj
                collection.status = 'New'
                collection.save()
                collection.items.all().delete()
                action_msg = "updated"
            else:
                collection = Collection.objects.create(
                    collector=collector,
                    date=date_obj,
                    client=client,
                    status='New',
                    total_amount=Decimal('0.0000')
                )
                action_msg = "saved"
            
            total_amt = Decimal('0.0000')
            
            for item_key in selected_ids:
                type_str, id_str = item_key.split('_')
                
                amount_val = request.POST.get(f'amount_{item_key}')
                try:
                    amt = Decimal(str(amount_val or 0))
                except (ValueError, TypeError, decimal.InvalidOperation):
                    amt = Decimal('0.0000')
                
                if amt > 0:
                    remark_val = request.POST.get(f'remark_{item_key}', '')
                    CollectionItem.objects.create(
                        collection=collection,
                        transaction_id=id_str,
                        transaction_type=type_str,
                        amount=amt,
                        collected_amount=amt,
                        is_credit=False,
                        remark=remark_val
                    )
                    total_amt += amt
            
            collection.total_amount = total_amt
            collection.save()
            
            messages.success(request, f"Collection {action_msg} successfully.")
            return redirect('add_collection')
            
        except Exception as e:
            logger.exception("Error saving collection")
            messages.error(request, "An error occurred while saving the collection.")
            return redirect('add_collection')

class CollectionListView(View):
    def get(self, request):
        client = getClient(request.user)
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        collector_id = request.GET.get('collector')
        date_str = request.GET.get('date')
        
        selected_collector = None
        if collector_id:
            # Authorization: Ensure collector belongs to user's client
            selected_collector = get_object_for_user(Collectors, request.user, id=collector_id)
            
        collections = Collection.objects.none()
        total_assigned = Decimal('0.0000')
        total_collected = Decimal('0.0000')

        if date_str:
            collections = Collection.objects.filter(client=client, status='Approved').order_by('-date')
            
            if collector_id:
                collections = collections.filter(collector_id=collector_id)
            
            try:
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                collections = collections.filter(date=date_obj)
                
                collections = collections.annotate(collected_total=Sum('items__collected_amount'))
                
                total_assigned = collections.aggregate(sum=Sum('total_amount'))['sum'] or Decimal('0.0000')
                total_collected = CollectionItem.objects.filter(collection__in=collections).aggregate(sum=Sum('collected_amount'))['sum'] or Decimal('0.0000')
            except ValueError:
                pass


        context = {
            'collectors': collectors,
            'collections': collections,
            'selected_collector': selected_collector,
            'selected_date': date_str,
            'total_assigned': total_assigned,
            'total_collected': total_collected,
        }
        return render(request, 'view_collections/collection_list.html', context)

class CollectionDetailView(View):
    def get(self, request, id):
        client = getClient(request.user)
        collection = get_object_or_404(Collection, id=id, client=client)
        items = collection.items.all()
        
        for item in items:
            item.partner_name = "-"
            item.partner_phone = "-"
            
            if item.transaction_type == 'Customer':
                c = Customers.objects.filter(id=item.transaction_id).first()
                if c:
                    item.partner_name = c.name
                    item.partner_phone = c.phone
            elif item.transaction_type == 'Supplier':
                s = Suppliers.objects.filter(id=item.transaction_id).first()
                if s:
                    item.partner_name = s.name
                    item.partner_phone = s.phone
            

            elif item.transaction_type == 'Sale':
                sale = Sales.objects.filter(sale_no=item.transaction_id, client=client).first()
                if sale and sale.customer:
                    item.partner_name = sale.customer.name
                    item.partner_phone = sale.customer.phone
        
        total_collected = sum((item.collected_amount for item in items), Decimal('0.0000'))
        
        context = {
            'collection': collection,
            'items': items,
            'total_collected': total_collected,
        }
        return render(request, 'view_collections/collection_detail.html', context)

def delete_collection(request, id):
    if request.method != 'POST':
        return redirect('collection_list')
    client = getClient(request.user)
    collection = get_object_or_404(Collection, id=id, client=client)
    collection.delete()
    messages.success(request, "Collection deleted successfully.")
    return redirect('collection_list')