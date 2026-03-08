
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from datetime import datetime, timedelta
from core.models import (
    Godowns, Sales, Suppliers, NSDs, Customers, Expenses, CashBanks, 
    Collectors, Purchases, Commissions, Cashs, StockTransfers, Collection
)
from core.views import getClient, update_ledger
from core.utils import get_next_id_generic
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse
import openpyxl
from io import BytesIO
from django.apps import apps
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from core.decorators import admin_action_required

class AddressView(View):
    def get(self, request):
        client = getClient(request.user)
        godowns = Godowns.objects.filter(is_active=True, client=client)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        return render(request, 'stock_view/address_view.html', {
            'godowns': godowns,
            'suppliers': suppliers
        })

    def post(self, request):
        client = getClient(request.user)
        date_from_str = request.POST.get('date_from')
        date_to_str = request.POST.get('date_to')
        party_id = request.POST.get('party_id')
        is_nsd = request.POST.get('is_nsd') == 'on'

        godowns = Godowns.objects.filter(is_active=True, client=client)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)

        transactions = []
        
        if date_from_str and date_to_str and party_id:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                
                if is_nsd:
                    nsds = NSDs.objects.filter(
                        client=client,
                        is_active=True,
                        date__range=[date_from, date_to],
                        sender_supplier_id=party_id
                    ).order_by('date')
                    for i, n in enumerate(nsds, start=1):
                        transactions.append({
                            'slno': i, 
                            'description': n.description,
                            'qty': n.qty,
                            'date': n.date,
                            'ref_no': n.nsd_no
                        })
                else:
                    sales = Sales.objects.filter(
                        client=client,
                        is_active=True,
                        date__range=[date_from, date_to],
                         godown_id=party_id
                    ).order_by('date')
                    for i, s in enumerate(sales, start=1):
                        transactions.append({
                            'slno': i,
                            'description': s.description,
                            'qty': s.qty,
                            'date': s.date,
                            'ref_no': s.sale_no
                        })
                        
            except ValueError:
                pass
        
        if request.POST.get('export') == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Address View Report"
            
            # Header
            headers = ["Sl No", "Date", "Description", "Qty"]
            ws.append(headers)
            
            for item in transactions:
                # Date format
                d_str = item['date'].strftime("%d-%m-%Y") if item['date'] else ""
                row = [
                    item['slno'],
                    d_str,
                    item['description'],
                    item['qty']
                ]
                ws.append(row)
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="address_view_report.xlsx"'
            return response

        # Prepare WhatsApp data for NSD supplier or Godown
        supplier_name = ''
        supplier_wa_number = ''
        if party_id and transactions:
            if is_nsd:
                try:
                    supplier_obj = Suppliers.objects.get(id=party_id, is_active=True, client=client)
                    supplier_name = supplier_obj.name or ''
                    if supplier_obj.country_code and supplier_obj.wa:
                        cc = str(supplier_obj.country_code).strip().replace('+', '')
                        num = str(supplier_obj.wa).strip().replace(' ', '').replace('-', '')
                        supplier_wa_number = f'{cc}{num}'
                except Suppliers.DoesNotExist:
                    pass
            else:
                try:
                    godown_obj = Godowns.objects.get(id=party_id, is_active=True, client=client)
                    supplier_name = godown_obj.name or ''
                    if godown_obj.country_code and godown_obj.wa:
                        cc = str(godown_obj.country_code).strip().replace('+', '')
                        num = str(godown_obj.wa).strip().replace(' ', '').replace('-', '')
                        supplier_wa_number = f'{cc}{num}'
                except Godowns.DoesNotExist:
                    pass

        return render(request, 'stock_view/address_view.html', {
            'godowns': godowns,
            'suppliers': suppliers,
            'transactions': transactions,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'selected_party': party_id,
            'is_nsd': is_nsd,
            'supplier_name': supplier_name,
            'supplier_wa_number': supplier_wa_number,
        })

@method_decorator([login_required, admin_action_required], name='dispatch')
class RecycleBinView(View):
    def get(self, request):
        client = getClient(request.user)
        
        models_to_check = [
            (Customers, 'Customer', 'customerId'),
            (Suppliers, 'Supplier', 'supplierId'),
            (Expenses, 'Expense', 'expenseId'),
            (Godowns, 'Godown', 'godownId'),
            (CashBanks, 'Cash Bank', 'cashbankId'),
            (Collectors, 'Collector', 'collectorId'),
            (Purchases, 'Purchase', 'purchase_no'),
            (Sales, 'Sale', 'sale_no'),
            (Commissions, 'Commission', 'commission_no'),
            (NSDs, 'NSD', 'nsd_no'),
            (Cashs, 'Cash', 'cash_no'),
            (StockTransfers, 'Stock Transfer', 'transfer_no'),
            (Collection, 'Collection', 'id'),
        ]
        
        categories = []
        for model, label, id_field in models_to_check:
            # Filter criteria: inactive, belongs to client, and has a deletion timestamp
            filters = {
                'is_active': False, 
                'client': client, 
                'deleted_at__isnull': False
            }
            # Exclude draft/held items if the model supports it
            if hasattr(model, 'hold'):
                filters['hold'] = False
                
            count = model.objects.filter(**filters).count()
            if count > 0:
                categories.append({
                    'label': label,
                    'model_name': model.__name__,
                    'count': count,
                    'icon': self.get_icon(label)
                })
        
        return render(request, 'recycle_bin/dashboard.html', {'categories': categories})

    def get_icon(self, label):
        icons = {
            'Customer': 'users',
            'Supplier': 'truck',
            'Expense': 'file-text',
            'Godown': 'home',
            'Cash Bank': 'landmark',
            'Collector': 'user-check',
            'Purchase': 'shopping-cart',
            'Sale': 'badge-dollar-sign',
            'Commission': 'percent',
            'NSD': 'arrow-right-left',
            'Cash': 'banknote',
            'Stock Transfer': 'package-2',
            'Collection': 'layers'
        }
        return icons.get(label, 'trash-2')

@method_decorator([login_required, admin_action_required], name='dispatch')
class RecycleBinListView(View):
    def get(self, request, model_name):
        client = getClient(request.user)
        model = apps.get_model('core', model_name)
        
        id_field_map = {
            'Customers': ('Customer', 'customerId'),
            'Suppliers': ('Supplier', 'supplierId'),
            'Expenses': ('Expense', 'expenseId'),
            'Godowns': ('Godown', 'godownId'),
            'CashBanks': ('Cash Bank', 'cashbankId'),
            'Collectors': ('Collector', 'collectorId'),
            'Purchases': ('Purchase', 'purchase_no'),
            'Sales': ('Sale', 'sale_no'),
            'Commissions': ('Commission', 'commission_no'),
            'NSDs': ('NSD', 'nsd_no'),
            'Cashs': ('Cash', 'cash_no'),
            'StockTransfers': ('Stock Transfer', 'transfer_no'),
            'Collection': ('Collection', 'id'),
        }
        
        label, id_field = id_field_map.get(model_name, (model_name, 'id'))
        
        # Consistent filtering with dashboard view
        filters = {
            'is_active': False, 
            'client': client, 
            'deleted_at__isnull': False
        }
        if hasattr(model, 'hold'):
            filters['hold'] = False
            
        items_query = model.objects.filter(**filters).order_by('-deleted_at')
        
        deleted_items = []
        for item in items_query:
            deleted_items.append({
                'id': item.id,
                'display_id': getattr(item, id_field) if id_field != 'id' else f"COL-{item.id}",
                'name': item.name if hasattr(item, 'name') else (item.category if hasattr(item, 'category') else label),
                'deleted_at': item.deleted_at,
                'details': self.get_item_details(model_name, item),
            })
            
        return render(request, 'recycle_bin/list.html', {
            'items': deleted_items,
            'label': label,
            'model_name': model_name
        })

    def get_item_details(self, model_name, item):
        """Return a list of (label, value) tuples with model-specific details."""
        details = []

        def fmt_date(d):
            return d.strftime('%d-%m-%Y') if d else '-'

        def fmt_decimal(v):
            try:
                return f'{float(v):,.2f}' if v else '-'
            except (TypeError, ValueError):
                return '-'

        def safe_name(obj):
            return obj.name if obj else '-'

        if model_name == 'Purchases':
            details = [
                ('Date', fmt_date(item.date)),
                ('Description', item.description or '-'),
                ('Qty', fmt_decimal(item.qty)),
                ('Rate', fmt_decimal(item.amount)),
                ('Total Amount', fmt_decimal(item.total_amount)),
                ('Godown', safe_name(item.godown)),
                ('Party', safe_name(item.supplier) if item.supplier else safe_name(item.customer)),
            ]
        elif model_name == 'Sales':
            details = [
                ('Date', fmt_date(item.date)),
                ('Description', item.description or '-'),
                ('Qty', fmt_decimal(item.qty)),
                ('Rate', fmt_decimal(item.amount)),
                ('Total Amount', fmt_decimal(item.total_amount)),
                ('Godown', safe_name(item.godown)),
                ('Party', safe_name(item.customer) if item.customer else safe_name(item.supplier)),
            ]
        elif model_name == 'Commissions':
            details = [
                ('Date', fmt_date(item.date)),
                ('Description', item.description or '-'),
                ('Qty', fmt_decimal(item.qty)),
                ('Rate', fmt_decimal(item.amount)),
                ('Total Amount', fmt_decimal(item.total_amount)),
                ('Godown', safe_name(item.godown)),
            ]
        elif model_name == 'NSDs':
            details = [
                ('Date', fmt_date(item.date)),
                ('Description', item.description or '-'),
                ('Qty', fmt_decimal(item.qty)),
                ('Sell Rate', fmt_decimal(item.sell_rate)),
                ('Sell Amount', fmt_decimal(item.sell_amount)),
                ('Purchase Rate', fmt_decimal(item.purchase_rate)),
                ('Purchase Amount', fmt_decimal(item.purchase_amount)),
                ('Sender', safe_name(item.sender)),
                ('Receiver', safe_name(item.receiver)),
            ]
        elif model_name == 'Cashs':
            details = [
                ('Date', fmt_date(item.date)),
                ('Transaction', item.transaction or '-'),
                ('Amount', fmt_decimal(item.amount)),
                ('Party', safe_name(item.customer) if item.customer else safe_name(item.supplier)),
                ('Cash/Bank', safe_name(item.cash_bank)),
                ('Description', item.description or '-'),
            ]
        elif model_name == 'StockTransfers':
            details = [
                ('Date', fmt_date(item.date)),
                ('Qty', fmt_decimal(item.qty)),
                ('From Godown', safe_name(item.transfer_from)),
                ('To Godown', safe_name(item.transfer_to)),
                ('Description', item.description or '-'),
            ]
        elif model_name == 'Expenses':
            details = [
                ('Category', item.category or '-'),
                ('Amount', fmt_decimal(item.amount)),
                ('Description', item.description or '-'),
            ]
        elif model_name == 'Collection':
            details = [
                ('Date', fmt_date(item.date)),
                ('Total Amount', fmt_decimal(item.total_amount)),
                ('Collector', safe_name(item.collector)),
                ('Status', item.status or '-'),
            ]
        elif model_name == 'Customers':
            details = [
                ('Phone', item.phone or '-'),
                ('Address', item.address or '-'),
            ]
        elif model_name == 'Suppliers':
            details = [
                ('Phone', item.phone or '-'),
                ('Address', item.address or '-'),
            ]
        elif model_name == 'Godowns':
            details = [
                ('Phone', item.phone or '-'),
                ('Address', item.address or '-'),
            ]
        elif model_name == 'CashBanks':
            details = [
                ('Description', item.description or '-'),
            ]
        elif model_name == 'Collectors':
            details = [
                ('Phone', item.phone or '-'),
                ('Address', item.address or '-'),
            ]

        return details

@method_decorator([login_required, admin_action_required], name='dispatch')
class RestoreView(View):
    def post(self, request, model_name, pk):
        client = getClient(request.user)
        model = apps.get_model('core', model_name)
        item = get_object_or_404(model, id=pk, client=client)
        
        id_field_map = {
            'Customers': 'customerId',
            'Suppliers': 'supplierId',
            'Expenses': 'expenseId',
            'Godowns': 'godownId',
            'CashBanks': 'cashbankId',
            'Collectors': 'collectorId',
            'Purchases': 'purchase_no',
            'Sales': 'sale_no',
            'Commissions': 'commission_no',
            'NSDs': 'nsd_no',
            'Cashs': 'cash_no',
            'StockTransfers': 'transfer_no',
            'Collection': 'id',
        }
        
        with transaction.atomic():
            # Handle ID conflict: assign new ID if original is already taken
            id_field = id_field_map.get(model_name)
            if id_field and id_field != 'id':
                current_id = getattr(item, id_field)
                if model.objects.filter(is_active=True, client=client, **{id_field: current_id}).exists():
                    new_id = get_next_id_generic(model_name, client)
                    if new_id:
                        setattr(item, id_field, new_id)
            
            # Re-apply side-effects that were reversed on delete
            self._reapply_side_effects(model_name, item)
            
            item.is_active = True
            item.deleted_at = None
            item.save()
        
        return JsonResponse({'status': 'success', 'message': 'Item restored successfully'})

    def _reapply_side_effects(self, model_name, item):
        """Re-apply ledger, godown, and cashbank side-effects on restore.
        This mirrors the reverse of each model's delete function.
        Uses refresh_from_db() + direct arithmetic (NOT F expressions)
        to avoid stale in-memory state on cached FK objects."""
        is_hold = getattr(item, 'hold', False)
        if is_hold:
            return  # Held items never had side-effects applied

        if model_name == 'Purchases':
            party = item.supplier if item.supplier else item.customer
            update_ledger(
                where=party, to=None,
                old_purchase=0, new_purchase=item.total_amount,
                old_sale=0, new_sale=0
            )
            if item.godown:
                item.godown.refresh_from_db()
                item.godown.qty += item.qty
                item.godown.save()

        elif model_name == 'Sales':
            party = item.customer if item.customer else item.supplier
            update_ledger(
                where=None, to=party,
                old_purchase=0, new_purchase=0,
                old_sale=0, new_sale=item.total_amount
            )
            if item.godown:
                item.godown.refresh_from_db()
                item.godown.qty -= item.qty
                item.godown.save()

        elif model_name == 'Cashs':
            if item.cash_bank:
                item.cash_bank.refresh_from_db()
                if item.transaction == 'Received':
                    item.cash_bank.balance += item.amount
                else:
                    item.cash_bank.balance -= item.amount
                item.cash_bank.save()

            party = item.customer if item.customer else item.supplier
            if item.transaction == 'Paid':
                update_ledger(where=None, to=party, old_sale=0, new_sale=item.amount)
            else:
                update_ledger(where=party, to=None, old_purchase=0, new_purchase=item.amount)

        elif model_name == 'NSDs':
            update_ledger(
                where=item.sender, to=item.receiver,
                old_purchase=0, new_purchase=item.purchase_amount,
                old_sale=0, new_sale=item.sell_amount
            )

        elif model_name == 'Commissions':
            if item.godown:
                item.godown.refresh_from_db()
                item.godown.qty -= item.qty
                item.godown.save()

        elif model_name == 'StockTransfers':
            if item.transfer_from:
                item.transfer_from.refresh_from_db()
                item.transfer_from.qty -= item.qty
                item.transfer_from.save()
            if item.transfer_to:
                item.transfer_to.refresh_from_db()
                item.transfer_to.qty += item.qty
                item.transfer_to.save()

@method_decorator([login_required, admin_action_required], name='dispatch')
class PermanentDeleteView(View):
    def post(self, request, model_name, pk):
        client = getClient(request.user)
        model = apps.get_model('core', model_name)
        item = get_object_or_404(model, id=pk, client=client)
        item.delete()
        return JsonResponse({'status': 'success', 'message': 'Item permanently deleted'})
