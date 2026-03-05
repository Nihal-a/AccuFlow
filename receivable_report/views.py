from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Sum, Q, F
from datetime import datetime
from decimal import Decimal
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs
from core.views import getClient, calculate_customer_balance, calculate_supplier_balance
import openpyxl
from io import BytesIO
try:
    from weasyprint import HTML, CSS
except ImportError:
    pass 
from weasyprint import HTML

class ReceivableReportView(View):
    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        date_to_str = request.POST.get("dateTo")
        
        date_limit = None
        if date_to_str:
            try:
                date_limit = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        min_amount_str = request.POST.get("minAmount")
        min_amount = None

        if min_amount_str:
            try:
                min_amount = Decimal(str(min_amount_str or 0))
            except ValueError:
                min_amount = None
        
        # Optimization: If no date filter is applied, do not show any data initially
        if not date_to_str:
             return render(request, 'receivable_report/receivable_report.html', {
                'receivables': [],
                'total_amount': Decimal('0.0000'),
                'date_to': '',
            })
        
        receivables = []
        
        customers = Customers.objects.filter(is_active=True, client=client)
        for c in customers:
            balance = calculate_customer_balance(c, client, date_limit=date_limit)

            show_item = False
            if min_amount is not None:
                if balance >= min_amount:
                    show_item = True
            elif balance > 0:
                show_item = True

            if show_item:
                receivables.append({
                    'code': c.customerId,
                    'name': c.name,
                    'phone': c.phone,
                    'amount': balance,
                    'type': 'customer'
                })

        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        for s in suppliers:
            balance = calculate_supplier_balance(s, client, date_limit=date_limit)

            show_item = False
            if min_amount is not None:
                if balance >= min_amount:
                     show_item = True
            elif balance > 0:
                 show_item = True

            if show_item: 
                receivables.append({
                    'code': s.supplierId,
                    'name': s.name,
                    'phone': s.phone, 
                    'amount': balance,
                    'type': 'supplier'
                })

        receivables.sort(key=lambda x: x['name'])

        total_amount = sum((item['amount'] for item in receivables), Decimal('0.0000'))

        paginator = Paginator(receivables, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'receivables': page_obj.object_list,
            'page_obj': page_obj,
            'total_amount': total_amount,
            'date_to': date_to_str,
            'min_amount': min_amount_str or ''
        }

        export_type = request.POST.get('export')
        
        if export_type == 'pdf':
            html_string = render_to_string('receivable_report/receivable_report_pdf.html', context)
            pdf_file = HTML(string=html_string).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="receivable_report.pdf"'
            return response
        
        elif export_type == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Receivable Report"
            
            headers = ["Code", "Name", "Phone", "Amount"]
            ws.append(headers)
            
            for item in receivables:
                row = [
                    item['code'],
                    item['name'],
                    item['phone'],
                    item['amount']
                ]
                ws.append(row)
            
            ws.append(["", "", "TOTAL", total_amount])
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="receivable_report.xlsx"'
            return response

        return render(request, 'receivable_report/receivable_report.html', context)

    def calculate_balance(self, entity, client, date_limit, is_customer=True):
        # Redundant: Refactored to use core.views functions
        pass
