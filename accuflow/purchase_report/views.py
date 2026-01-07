from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q
from datetime import datetime
from core.models import Suppliers, Purchases, Customers
from core.views import getClient

class PurchaseReportView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = list(Suppliers.objects.filter(is_active=True, client=client))
        customers = list(Customers.objects.filter(is_active=True, client=client))
        
        # Combine them into a single list for the dropdown
        # Assuming both models have 'id' and 'name' which is true
        # We need a way to distinguish them if IDs overlap, but for simple dropdown filter 
        # based on 'supplier_id' in filter_kwargs, it implies Purchases model links to Supplier OR Customer? 
        # Looking at Purchase model: 
        # supplier = ForeignKey(Suppliers...)
        # customer = ForeignKey(Customers...)
        # So we need to handle "selected ID" being for a Supplier OR a Customer. 
        # We should pass them separately or mark them.
        # But user request says "include customer too in the supplier list".
        # Let's pass a combined list of dicts or objects with a 'type' flag.

        combined_partners = []
        for s in suppliers:
             combined_partners.append({'id': s.id, 'name': s.name, 'type': 'supplier'})
        
        for c in customers:
             combined_partners.append({'id': c.id, 'name': c.name, 'type': 'customer'})

        context = {
            'trade_partners': combined_partners,
            'date_from': '',
            'date_to': '',
        }
        return render(request, 'purchase_report/purchase_report.html', context)

    def post(self, request):
        client = getClient(request.user)
        # We expect value to be "type_id" e.g. "supplier_12" or "customer_5"
        filter_value = request.POST.get('supplier') 
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        sort = request.POST.get('sort')

        suppliers = list(Suppliers.objects.filter(is_active=True, client=client))
        customers = list(Customers.objects.filter(is_active=True, client=client))
        
        combined_partners = []
        for s in suppliers:
             combined_partners.append({'id': s.id, 'name': s.name, 'type': 'supplier'})
        
        for c in customers:
             combined_partners.append({'id': c.id, 'name': c.name, 'type': 'customer'})

        filter_kwargs = {
            'client': client,
            'is_active': True,
            'hold': False
        }

        selected_id = None
        selected_type = None

        if filter_value:
            try:
                p_type, p_id = filter_value.split('_')
                if p_type == 'supplier':
                    filter_kwargs['supplier_id'] = p_id
                elif p_type == 'customer':
                    filter_kwargs['customer_id'] = p_id
                
                selected_id = p_id
                selected_type = p_type
            except ValueError:
                pass
        
        if date_from_str:
            filter_kwargs['date__gte'] = date_from_str
        
        if date_to_str:
            filter_kwargs['date__lte'] = date_to_str

        date_from = date_from_str
        date_to = date_to_str

        purchases = Purchases.objects.filter(**filter_kwargs)
        
        # Sorting
        if sort == 'Serial':
            purchases = purchases.order_by('purchase_no')
        else:
            # Default sort by date
            purchases = purchases.order_by('date', 'created_at')

        # Calculate totals
        total_qty = purchases.aggregate(Sum('qty'))['qty__sum'] or 0
        total_amount = purchases.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        # Prepare list for display to handle "Trade Partner" and description logic easily if needed
        # Although we can do it in template, doing it here keeps it clean
        report_data = []
        for p in purchases:
            # Determine Trade Partner Name
            if p.supplier:
                partner_name = p.supplier.name
            elif p.customer:
                partner_name = p.customer.name
            else:
                partner_name = "Unknown"
            
            # Description logic based on sort/filter preference from previous code? 
            # User said "description auto fill like from -> to as description" in previous turn for Stock Transfer.
            # For Purchase, "Detailed" vs "Remark" was in old code. 
            # Let's keep it simple: use p.description
            description = p.description

            report_data.append({
                'trade_partner': partner_name,
                'date': p.date,
                'transaction_no': p.purchase_no,
                'description': description,
                'qty': p.qty,
                'rate': p.amount,
                'total_amount': p.total_amount
            })

        context = {
            'trade_partners': combined_partners,
            'purchases': report_data,
            'total_qty': total_qty,
            'total_amount': total_amount,
            'date_from': date_from,
            'date_to': date_to,
            'selected_filter_value': filter_value if filter_value else '',
            'sort': sort
        }

        return render(request, 'purchase_report/purchase_report.html', context)