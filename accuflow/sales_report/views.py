from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q
from datetime import datetime
from core.models import Customers, Sales, Suppliers 
from core.views import getClient

class SalesReportView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = list(Suppliers.objects.filter(is_active=True, client=client))
        customers = list(Customers.objects.filter(is_active=True, client=client))
        
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
        return render(request, 'sales_report/sales_report.html', context)

    def post(self, request):
        client = getClient(request.user)
        filter_value = request.POST.get('customer') # reusing same logic, maybe name is trade_partner in template? we will stick to 'customer' as input name or change in template
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

        sales = Sales.objects.filter(**filter_kwargs)
        
        # Sorting
        if sort == 'Serial':
            sales = sales.order_by('sale_no')
        else:
            # Default sort by date
            sales = sales.order_by('date', 'created_at')

        # Calculate totals
        total_qty = sales.aggregate(Sum('qty'))['qty__sum'] or 0
        total_amount = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        # Prepare list for display 
        report_data = []
        for s in sales:
            # Determine Trade Partner Name
            if s.supplier:
                partner_name = s.supplier.name
            elif s.customer:
                partner_name = s.customer.name
            else:
                partner_name = "Unknown"
            
            description = s.description

            report_data.append({
                'trade_partner': partner_name,
                'date': s.date,
                'transaction_no': s.sale_no,
                'description': description,
                'qty': s.qty,
                'rate': s.amount,
                'total_amount': s.total_amount
            })

        context = {
            'trade_partners': combined_partners,
            'sales': report_data,
            'total_qty': total_qty,
            'total_amount': total_amount,
            'date_from': date_from,
            'date_to': date_to,
            'selected_filter_value': filter_value if filter_value else '',
            'sort': sort
        }

        return render(request, 'sales_report/sales_report.html', context)