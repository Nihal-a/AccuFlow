from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from core.views import getClient
from datetime import datetime
from django.utils import timezone
from .services import BalanceSheetService

class BalanceSheetView(LoginRequiredMixin, View):
    template_name = 'balance_sheet/balance_sheet.html'

    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        
        today = timezone.localtime(timezone.now()).date()
        date_to_str = request.POST.get("dateTo") or request.GET.get("dateTo") # Format YYYY-MM-DD

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                date_to = today
        else:
            date_to = today

        data = BalanceSheetService.get_balance_sheet(client, date_to)

        context = {
            'accounts': data['accounts'],
            'total_debit': data['total_debit'],
            'total_credit': data['total_credit'],
            'is_balanced': data['is_balanced'],
            'difference': data['difference'],
            'date_to': date_to.strftime("%Y-%m-%d"),
            'today': today
        }
        
        
        return render(request, self.template_name, context)
