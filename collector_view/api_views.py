from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from core.models import Collectors, Collection, Sales, CollectionItem, Purchases, NSDs, Customers, Suppliers
from django.http import JsonResponse
import datetime
import json
import logging
from decimal import Decimal, InvalidOperation



logger = logging.getLogger(__name__)


class CollectorUpdateItemView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
         return self.request.user.is_authenticated and self.request.user.is_collector

    def post(self, request, id):
        try:
            item = get_object_or_404(CollectionItem, id=id)
            # Verify collector owns this collection
            if item.collection.collector.user != request.user:
                 return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            if item.collection.status not in ['New', 'Rejected']:
                 return JsonResponse({'status': 'error', 'message': 'Collection is not editable'}, status=400)

            data = json.loads(request.body)
            amount = data.get('amount')
            remark = data.get('remark')
            
            # Handle empty amount string as 0
            if amount is not None:
                if amount == '':
                    item.collected_amount = Decimal('0.0000')
                else:
                    try:
                        item.collected_amount = Decimal(str(amount))
                    except (ValueError, TypeError, InvalidOperation):
                         pass # Keep valid value or 0
            
            if remark is not None:
                item.remark = remark
            
            item.save()
            
            # Recalculate total for UI update if needed? 
            # Not strictly necessary if frontend handles summing, but good hygiene
            # collection = item.collection
            # collection.total_collected = ... (We compute this on fly usually)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error updating collection item: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'}, status=500)


class CollectorReorderItemsView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
         return self.request.user.is_authenticated and self.request.user.is_collector

    def post(self, request, id):
        try:
            collection = get_object_or_404(Collection, id=id)
            # Verify collector owns this collection
            if collection.collector.user != request.user:
                 return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            if collection.status not in ['New', 'Rejected']:
                 return JsonResponse({'status': 'error', 'message': 'Collection is not editable'}, status=400)

            data = json.loads(request.body)
            item_orders = data.get('orders', [])
            
            # orders should be a list of dicts: [{'id': 1, 'order': 0}, {'id': 2, 'order': 1}]
            for item_data in item_orders:
                item_id = item_data.get('id')
                order_index = item_data.get('order')
                
                if item_id is not None and order_index is not None:
                    # Update item order, checking it belongs to this collection
                    CollectionItem.objects.filter(id=item_id, collection=collection).update(order=order_index)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error reordering collection items: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'}, status=500)
