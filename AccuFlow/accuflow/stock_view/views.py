from django.forms import FloatField
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q, Value, CharField, F
from datetime import datetime

from django.forms import FloatField
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum, Q, Value, CharField, F
from datetime import datetime
from core.views import getClient
from core.models import Godowns, Purchases, Sales

class StockView(View):
    def get(self, request):
        godowns = Godowns.objects.filter(is_active=True, client=getClient(request.user))
        return render(request,'stock_view/stock_view.html',{'godowns':godowns, 'sort': 'Serial'})
    
    def parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return None

    def post(self, request):
        date_to_str = request.POST.get("dateTo")
        client = getClient(request.user)

        godowns = Godowns.objects.filter(is_active=True, client=client)

        context = {
            'godowns': godowns,
            'date_to': date_to_str,
            'stocks': [],
            'total_qty_all': 0,
            'total_amount_all': 0,
            'total_avg_rate_all': 0,
        }
        
        if not date_to_str:
            return render(request, 'stock_view/stock_view.html', context)

        date_to = self.parse_date(date_to_str)

        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()

        if date_to:
            date_filter &= Q(date__lte=date_to)

        purchases = Purchases.objects.filter(base_filter, date_filter)
        sales = Sales.objects.filter(base_filter, date_filter)

        stocks = {}

        for p in purchases:
            g = p.godown
            if not g:
                continue

            if g.id not in stocks:
                stocks[g.id] = {
                    'godown': g,
                    'purchase_qty': 0,    
                    'purchase_value': 0, 
                    'balance_qty': 0,    
                    'avg_rate': 0,
                    'total_amount': 0,
                }

            stocks[g.id]['purchase_qty'] += p.qty
            stocks[g.id]['purchase_value'] += p.qty * p.amount
            stocks[g.id]['balance_qty'] += p.qty  

        for s in sales:
            g = s.godown
            if not g:
                continue

            if g.id not in stocks:
                stocks[g.id] = {
                    'godown': g,
                    'purchase_qty': 0,
                    'purchase_value': 0,
                    'balance_qty': 0,
                    'avg_rate': 0,
                    'total_amount': 0,
                }

            stocks[g.id]['balance_qty'] -= s.qty

        total_qty_all = 0
        total_value_all = 0

        for item in stocks.values():
            balance_qty = item['balance_qty']
            purchase_value = item['purchase_value']
            purchase_qty = item['purchase_qty']

            avg = (purchase_value / purchase_qty) if purchase_qty else 0
            item['avg_rate'] = round(avg, 2)

            item['total_amount'] = round(balance_qty * avg, 2)

            item['total_qty'] = round(balance_qty, 3)  

            total_qty_all += balance_qty
            total_value_all += balance_qty * avg 

        total_avg_rate_all = (total_value_all / total_qty_all) if total_qty_all else 0

        context['stocks'] = list(stocks.values())
        context['total_qty_all'] = round(total_qty_all, 3)
        context['total_amount_all'] = round(total_value_all, 3)
        context['total_avg_rate_all'] = round(total_avg_rate_all, 2)

        return render(request, 'stock_view/stock_view.html', context)


