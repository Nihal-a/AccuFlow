from django.shortcuts import render,redirect, get_object_or_404
from core.models import Suppliers
from django.views import View
from core.views import getClient

class SupplierLedgerView(View):
    def get(self,request):
        supplierledgers = Suppliers.objects.all()
        return render(request,'supplier_ledger/supplier_ledger.html',{'supplierledgers':supplierledgers})

