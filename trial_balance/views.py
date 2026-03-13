from django.shortcuts import render
from django.db.models import Sum, Q, F
from django.views import View
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from core.models import Customers, Suppliers, Purchases, Sales, NSDs, Cashs, Expenses, Commissions, Godowns
from core.views import getClient
from django.template.loader import render_to_string
from django.http import HttpResponse

try:
    from weasyprint import HTML
except ImportError:
    pass

class TrialBalanceView(View):
    def get(self, request):
        return self.process_report(request)
    
    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        now = timezone.localtime(timezone.now())
        date_to_str = request.POST.get("dateTo") or now.strftime("%Y-%m-%d")
        
        try:
            date_limit = datetime.strptime(date_to_str, "%Y-%m-%d").date()
        except ValueError:
            date_limit = timezone.localtime(timezone.now()).date()
            
        from profit_loss.services import TrialBalanceService
        data = TrialBalanceService.get_trial_balance(client, date_limit)
        
        context = {
            'accounts': data['accounts'],
            'total_debit': data['total_debit'],
            'total_credit': data['total_credit'],
            'difference': data['difference'],
            'date_to': date_to_str,
            'is_balanced': data['is_balanced']
        }
        
        export_type = request.POST.get('export')
        if export_type == 'pdf':
             html_string = render_to_string('trial_balance/trial_balance_pdf.html', context)
             pdf_file = HTML(string=html_string).write_pdf()
             response = HttpResponse(pdf_file, content_type='application/pdf')
             response['Content-Disposition'] = 'inline; filename="trial_balance.pdf"'
             return response

        return render(request, 'trial_balance/trial_balance.html', context)
