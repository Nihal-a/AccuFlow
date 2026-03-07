from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from core.models import Suppliers, Purchases, Customers, NSDs
from core.views import getClient
import openpyxl
from io import BytesIO
try:
    from weasyprint import HTML, CSS
except ImportError:
    pass 
from weasyprint import HTML

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
             combined_partners.append({'id': s.id, 'name': s.name, 'type': 'supplier', 'key': f"supplier_{s.id}"})
        
        for c in customers:
             combined_partners.append({'id': c.id, 'name': c.name, 'type': 'customer', 'key': f"customer_{c.id}"})

        context = {
            'trade_partners': combined_partners,
            'date_from': '',
            'date_to': '',
            'report_type': 'all',
        }
        return render(request, 'purchase_report/purchase_report.html', context)

    def post(self, request):
        client = getClient(request.user)
        # We expect value to be "type_id" e.g. "supplier_12" or "customer_5"
        filter_value = request.POST.get('supplier') 
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        sort = request.POST.get('sort')
        report_type = request.POST.get('report_type', 'all') # all, regular, nsd

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
        
        nsd_filter_kwargs = {
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
                    nsd_filter_kwargs['sender_supplier_id'] = p_id
                elif p_type == 'customer':
                    filter_kwargs['customer_id'] = p_id
                    nsd_filter_kwargs['sender_customer_id'] = p_id
                
                selected_id = p_id
                selected_type = p_type
            except ValueError:
                pass
        
        if date_from_str:
            filter_kwargs['date__gte'] = date_from_str
            nsd_filter_kwargs['date__gte'] = date_from_str
        
        if date_to_str:
            filter_kwargs['date__lte'] = date_to_str
            nsd_filter_kwargs['date__lte'] = date_to_str
        min_amount_str = request.POST.get('min_amount')
        # Optimization/Requirement: Both Date From and Date To are mandatory
        if not date_from_str or not date_to_str:
             return render(request, 'purchase_report/purchase_report.html', {
                'trade_partners': combined_partners,
                'purchases': [],
                'total_qty': Decimal('0.0000'),
                'avg_rate': Decimal('0.0000'),
                'total_amount': Decimal('0.0000'),
                'date_from': date_from_str or '',
                'date_to': date_to_str or '',
                'selected_filter_value': '',
                'min_amount': min_amount_str or '',
                'report_type': report_type
            })
            
        if min_amount_str:
            try:
                min_amount = Decimal(str(min_amount_str or 0))
                if min_amount > 0:
                    filter_kwargs['total_amount__gte'] = min_amount
            except ValueError:
                pass

        date_from = date_from_str
        date_to = date_to_str

        combined_purchases = []

        if report_type in ['all', 'regular']:
            purchases = Purchases.objects.filter(**filter_kwargs)
            for p in purchases:
                if p.supplier:
                    partner_name = p.supplier.name
                elif p.customer:
                    partner_name = p.customer.name
                else:
                    partner_name = "Unknown"
                
                combined_purchases.append({
                    'type': 'PR',
                    'trade_partner': partner_name,
                    'date': p.date,
                    'transaction_no': str(p.purchase_no),
                    'description': p.description or '',
                    'qty': p.qty,
                    'rate': p.amount,
                    'total_amount': p.total_amount,
                    'created_at': p.created_at,
                    'original_obj': p
                })

        if report_type in ['all', 'nsd']:
            nsds = NSDs.objects.filter(**nsd_filter_kwargs)
            # Apply min_amount to NSDs based on purchase_amount
            for n in nsds:
                if min_amount_str:
                    try:
                        if n.purchase_amount < Decimal(str(min_amount_str)):
                            continue
                    except:
                        pass
                
                if n.sender:
                    partner_name = n.sender.name
                else:
                    partner_name = "Unknown"
                    
                combined_purchases.append({
                    'type': 'NS',
                    'trade_partner': partner_name,
                    'date': n.date,
                    'transaction_no': str(n.nsd_no),
                    'description': n.description or '',
                    'qty': n.qty,
                    'rate': n.purchase_rate,
                    'total_amount': n.purchase_amount,
                    'created_at': n.created_at,
                    'original_obj': n
                })

        # Sorting
        min_dt = timezone.make_aware(datetime.min) if timezone.get_current_timezone() else datetime.min
        if sort == 'Serial':
            # Serial sort fallback to date since PR and NS numbers are independent
            combined_purchases.sort(key=lambda x: (x['date'], x.get('created_at') or min_dt))
        else:
            combined_purchases.sort(key=lambda x: (x['date'], x.get('created_at') or min_dt))

        # Calculate totals
        total_qty = sum((item['qty'] or Decimal('0')) for item in combined_purchases)
        total_amount = sum((item['total_amount'] or Decimal('0')) for item in combined_purchases)
        
        avg_rate = Decimal('0.00')
        if total_qty > 0:
            avg_rate = total_amount / total_qty

        # Pagination
        paginator = Paginator(combined_purchases, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Prepare list for display
        report_data = []
        for item in page_obj.object_list:
            report_data.append(item)

        context = {
            'trade_partners': combined_partners,
            'purchases': report_data,
            'page_obj': page_obj,
            'total_qty': total_qty,
            'avg_rate': avg_rate,
            'total_amount': total_amount,
            'date_from': date_from,
            'date_to': date_to,
            'selected_filter_value': filter_value if filter_value else '',
            'min_amount': min_amount_str or '',
            'sort': sort,
            'report_type': report_type
        }

        export_type = request.POST.get('export')
        
        if export_type == 'pdf':
            context['selected_filter_name'] = ""
            if selected_id and selected_type:
                for p in combined_partners:
                    if p['key'] == filter_value:
                        context['selected_filter_name'] = f"{p['name']} ({p['type'].title()})"
                        break
            
            html_string = render_to_string('purchase_report/purchase_report_pdf.html', context)
            pdf_file = HTML(string=html_string).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="purchase_report.pdf"'
            return response
        
        elif export_type == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Purchase Report"
            
            headers = ["#", "Type", "Trade Partner", "Date", "Transaction No", "Description", "Qty", "Rate", "Amount"]
            ws.append(headers)
            
            for index, item in enumerate(report_data, 1):
                d_str = item['date'].strftime("%d-%m-%Y") if item['date'] else ""
                row = [
                    index,
                    item['type'],
                    item['trade_partner'],
                    d_str,
                    item['transaction_no'],
                    item['description'],
                    item['qty'],
                    item['rate'],
                    item['total_amount']
                ]
                ws.append(row)
            
            ws.append(["", "", "", "", "", "TOTAL", total_qty, avg_rate, total_amount])
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="purchase_report.xlsx"'
            return response

        return render(request, 'purchase_report/purchase_report.html', context)