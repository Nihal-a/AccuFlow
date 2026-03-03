
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from datetime import datetime, timedelta
from core.models import (
    Godowns, Sales, Suppliers, NSDs, Customers, Expenses, CashBanks, 
    Collectors, Purchases, Commissions, Cashs, StockTransfers, Collection
)
from core.views import getClient
from core.utils import get_next_id_generic
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

        # Prepare WhatsApp data for NSD supplier
        supplier_name = ''
        supplier_wa_number = ''
        if is_nsd and party_id and transactions:
            try:
                supplier_obj = Suppliers.objects.get(id=party_id, is_active=True, client=client)
                supplier_name = supplier_obj.name or ''
                if supplier_obj.country_code and supplier_obj.wa:
                    cc = str(supplier_obj.country_code).strip().replace('+', '')
                    num = str(supplier_obj.wa).strip().replace(' ', '').replace('-', '')
                    supplier_wa_number = f'{cc}{num}'
            except Suppliers.DoesNotExist:
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
            })
            
        return render(request, 'recycle_bin/list.html', {
            'items': deleted_items,
            'label': label,
            'model_name': model_name
        })

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
        }
        
        id_field = id_field_map.get(model_name)
        if id_field:
            current_id = getattr(item, id_field)
            if model.objects.filter(is_active=True, client=client, **{id_field: current_id}).exists():
                new_id = get_next_id_generic(model_name, client)
                if new_id:
                    setattr(item, id_field, new_id)
        
        item.is_active = True
        item.deleted_at = None
        item.save()
        return JsonResponse({'status': 'success', 'message': 'Item restored successfully'})

@method_decorator([login_required, admin_action_required], name='dispatch')
class PermanentDeleteView(View):
    def post(self, request, model_name, pk):
        client = getClient(request.user)
        model = apps.get_model('core', model_name)
        item = get_object_or_404(model, id=pk, client=client)
        item.delete()
        return JsonResponse({'status': 'success', 'message': 'Item permanently deleted'})
