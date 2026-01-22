from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View
from django.db.models import Sum, Q
from datetime import datetime
from core.models import Customers, Sales, Suppliers 
from core.views import getClient
import openpyxl
from io import BytesIO
try:
    from weasyprint import HTML, CSS
except ImportError:
    pass 
# Note: weasyprint import might fail if not installed properly, handled by try-except or let it error if strict requirement? 
# User sees weasyprint installed. Safe to import.
from weasyprint import HTML

class SalesReportView(View):
    def get(self, request):
        client = getClient(request.user)
        suppliers = list(Suppliers.objects.filter(is_active=True, client=client))
        customers = list(Customers.objects.filter(is_active=True, client=client))
        
        combined_partners = []
        for s in suppliers:
             combined_partners.append({'id': s.id, 'name': s.name, 'type': 'supplier', 'key': f"supplier_{s.id}"})
        
        for c in customers:
             combined_partners.append({'id': c.id, 'name': c.name, 'type': 'customer', 'key': f"customer_{c.id}"})

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
             combined_partners.append({'id': s.id, 'name': s.name, 'type': 'supplier', 'key': f"supplier_{s.id}"})
        
        for c in customers:
             combined_partners.append({'id': c.id, 'name': c.name, 'type': 'customer', 'key': f"customer_{c.id}"})

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
            
        # Optimization: If no date filter is applied, do not show any data initially
        min_amount_str = request.POST.get('min_amount')
        
        # Optimization: If no date filter is applied, do not show any data initially
        if not date_from_str and not date_to_str and not filter_value:
             return render(request, 'sales_report/sales_report.html', {
                'trade_partners': combined_partners,
                'sales': [],
                'total_qty': 0,
                'total_amount': 0,
                'date_from': '',
                'date_to': '',
                'selected_filter_value': '',
                'min_amount': min_amount_str or ''
            })
            
        if min_amount_str:
            try:
                min_amount = float(min_amount_str)
                if min_amount > 0:
                    filter_kwargs['total_amount__gte'] = min_amount
            except ValueError:
                pass

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
            'min_amount': min_amount_str or '',
            'sort': sort
        }

        export_type = request.POST.get('export')
        
        if export_type == 'pdf':
            # Add formatted date for report
            context['selected_filter_name'] = ""
            if selected_id and selected_type:
                # Find name
                for p in combined_partners:
                    if p['key'] == filter_value:
                        context['selected_filter_name'] = f"{p['name']} ({p['type'].title()})"
                        break
            
            html_string = render_to_string('sales_report/sales_report_pdf.html', context)
            pdf_file = HTML(string=html_string).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="sales_report.pdf"'
            return response
        
        elif export_type == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sales Report"
            
            # Header
            headers = ["#", "Trade Partner", "Date", "Transaction No", "Description", "Qty", "Rate", "Amount"]
            ws.append(headers)
            
            for index, item in enumerate(report_data, 1):
                # Date format
                d_str = item['date'].strftime("%d-%m-%Y") if item['date'] else ""
                row = [
                    index,
                    item['trade_partner'],
                    d_str,
                    item['transaction_no'],
                    item['description'],
                    item['qty'],
                    item['rate'],
                    item['total_amount']
                ]
                ws.append(row)
            
            # Totals
            ws.append(["", "", "", "", "TOTAL", total_qty, "", total_amount])
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="sales_report.xlsx"'
            return response

        return render(request, 'sales_report/sales_report.html', context)