from django.shortcuts import render,redirect, get_object_or_404
from core.models import Expenses
from django.views import View
from django.views.generic.edit import DeleteView

class PurchaseEntryView(View):
    def get(self,request):
        return render(request,'purchase_entry/purchase_entry.html')
