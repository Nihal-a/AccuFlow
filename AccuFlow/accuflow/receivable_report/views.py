from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View
from django.db.models import Sum, Q, F
from datetime import datetime
from decimal import Decimal
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs
from core.views import getClient
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
        date_from_str = request.POST.get("dateFrom")
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
        if not date_from_str and not date_to_str:
             return render(request, 'receivable_report/receivable_report.html', {
                'receivables': [],
                'total_amount': Decimal('0.0000'),
                'date_from': '',
                'date_to': '',
            })
        
        receivables = []
        
        customers = Customers.objects.filter(is_active=True, client=client)
        for c in customers:
            if date_limit:
                balance = self.calculate_balance(c, client, date_limit, is_customer=True)
            else:
                balance = c.balance 

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
            if date_limit:
                balance = self.calculate_balance(s, client, date_limit, is_customer=False)
            else:
                balance = s.balance 

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

        context = {
            'receivables': receivables,
            'total_amount': total_amount,
            'date_from': date_from_str,
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
        if is_customer:
            base_filter = Q(is_active=True, hold=False, client=client, customer=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_customer=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_customer=entity, date__lte=date_limit)
        else:
            base_filter = Q(is_active=True, hold=False, client=client, supplier=entity, date__lte=date_limit)
            nsd_sender_filter = Q(is_active=True, hold=False, client=client, sender_supplier=entity, date__lte=date_limit)
            nsd_receiver_filter = Q(is_active=True, hold=False, client=client, receiver_supplier=entity, date__lte=date_limit)

        purchases = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        
        nsd_sender_amt = NSDs.objects.filter(nsd_sender_filter).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        nsd_receiver_amt = NSDs.objects.filter(nsd_receiver_filter).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        # Balance = Debit - Credit
        debit_sum = sales + nsd_receiver_amt + cash_paid
        credit_sum = purchases + nsd_sender_amt + cash_received
        
        static_ob = Decimal(str(entity.open_debit or 0)) - Decimal(str(entity.open_credit or 0))
        
        return static_ob + (debit_sum - credit_sum)
