from django.shortcuts import render,redirect, get_object_or_404
from core.models import Godowns
from django.views import View
from core.views import getClient

class StockView(View):
    def get(self,request):
        stocks = Godowns.objects.all()
        return render(request,'stock_view/stock_view.html',{'stocks':stocks})

