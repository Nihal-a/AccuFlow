from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import PandLService, TrialBalanceService
from core.views import getClient
from datetime import datetime, date
from django.utils import timezone

class ProfitLossView(LoginRequiredMixin, View):
    template_name = 'profit_loss/pl_report.html'

    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        
        # Date Handling
        today = timezone.localtime(timezone.now()).date()
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo") or request.GET.get("dateTo")

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                date_to = today
        else:
            date_to = today

        if date_from_str:
             try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
             except ValueError:
                 # Default to start of current year if invalid
                 date_from = date(today.year, 1, 1)
        else:
             # Default behavior: If only "Date As On" is provided (like in image),
             # we assume "From Beginning" or "This Fiscal Year". 
             # Let's default to Jan 1st of current year for now.
             date_from = date(date_to.year, 1, 1)

        data = PandLService.get_financial_data(client, date_from, date_to)

        context = {
            'data': data,
            'date_from': date_from.strftime("%Y-%m-%d"),
            'date_to': date_to.strftime("%Y-%m-%d"),
            'today': today
        }
        
        return render(request, self.template_name, context)

class TrialBalanceView(LoginRequiredMixin, View):
    template_name = 'profit_loss/trial_balance.html'

    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        
        today = timezone.localtime(timezone.now()).date()
        date_to_str = request.POST.get("dateTo") or request.GET.get("dateTo")

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            except ValueError:
                date_to = today
        else:
            date_to = today

        data = TrialBalanceService.get_trial_balance(client, date_to)

        context = {
            'accounts': data['accounts'],
            'total_debit': data['total_debit'],
            'total_credit': data['total_credit'],
            'difference': data['difference'],
            'is_balanced': data['is_balanced'],
            'date_to': date_to.strftime("%Y-%m-%d"),
            'today': today
        }
        
        return render(request, self.template_name, context)

