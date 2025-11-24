from django.shortcuts import render,redirect, get_object_or_404
from core.models import Suppliers
from django.views import View
from core.views import getClient
from core.models import *

class SupplierLedgerView(View):
    def get(self,request):
        suppliers = Suppliers.objects.filter(is_active=True,client = getClient(request.user))
        return render(request,'supplier_ledger/supplier_ledger.html',{'suppliers':suppliers})

    def post(self,request): 
        supplier = request.POST.get('supplier')
        suppliers = Suppliers.objects.filter(is_active=True,client = getClient(request.user))
        purchases = Purchases.objects.filter(is_active=True,hold=False,client = getClient(request.user))
        sales = Sales.objects.filter(is_active=True,hold=False,client = getClient(request.user))
        nsds = NSDs.objects.filter(is_active=True,hold=False,client = getClient(request.user))
        cashs = Cashs.objects.filter(is_active=True,hold=False,client = getClient(request.user))
        sender_nsds = []
        receiver_nsds = []
        date_from = None
        date_to = None
        ledgers = []
        date_from = request.POST.get("dateFrom")
        date_to = request.POST.get("dateTo")
        total_balance = 0
        if supplier:
            supplier = Suppliers.objects.get(id=supplier)

            sales = sales.filter(supplier=supplier)
            purchases = purchases.filter(supplier=supplier) 
            sender_nsds = nsds.filter(sender_supplier=supplier)
            receiver_nsds = nsds.filter(receiver_supplier=supplier)
            cashs = cashs.filter(supplier=supplier)

        if date_from:
            sales = sales.filter(date__gte=date_from)
            purchases = purchases.filter(date__gte=date_from)
            sender_nsds = sender_nsds.filter(date__gte=date_from)
            receiver_nsds = receiver_nsds.filter(date__gte=date_from)
            cashs = cashs.filter(date__gte=date_from)

        if date_to:
            sales = sales.filter(date__lte=date_to)
            purchases = purchases.filter(date__lte=date_to)
            sender_nsds = sender_nsds.filter(date__lte=date_to)
            receiver_nsds = receiver_nsds.filter(date__lte=date_to)
            cashs = cashs.filter(date__lte=date_to)
        
        for purchase in purchases:
            ledgers.append({
                'name':f'{purchase.purchase_no} - (Purchase)',
                'date':purchase.date,
                'supplier':purchase.supplier.name if purchase.supplier else '',
                'party':purchase.godown.name,
                'qty':purchase.qty,
                'rate':purchase.amount,
                'total_amount':purchase.total_amount,
                'description':purchase.description,
                'balance':purchase.seller_balance,
            })
        for sale in sales:
            ledgers.append({
                'name':f'{sale.sale_no} - (Sale)',
                'date':sale.date,
                'supplier':sale.supplier.name if sale.supplier else '',
                'party':sale.godown.name,
                'qty':sale.qty,
                'rate':sale.amount,
                'total_amount':sale.total_amount,
                'description':sale.description,
                'balance':sale.seller_balance,
            })
        for nsd in sender_nsds:
            ledgers.append({
                'name':f'{nsd.nsd_no} - (NSD)',
                'date':nsd.date,
                'supplier':nsd.sender_supplier.name if nsd.sender_supplier else '',
                'party':nsd.receiver.name if nsd.receiver_supplier else '',
                'qty':nsd.qty,
                'rate':nsd.sell_rate,
                'total_amount':nsd.sell_amount,
                'description':nsd.description,
                'balance':nsd.sender_balance,
            })
        for nsd in receiver_nsds:
            ledgers.append({
                'name':f'{nsd.nsd_no} - (NSD)',
                'date':nsd.date,
                'supplier':nsd.sender_supplier.name if nsd.sender_supplier else '',
                'party':nsd.receiver.name if nsd.receiver_supplier else '',
                'qty':nsd.qty,
                'rate':nsd.sell_rate,
                'total_amount':nsd.sell_amount,
                'description':nsd.description,
                'balance':nsd.receiver_balance,
            })
        for cash in cashs:
            ledgers.append({
                'name':f'{cash.cash_no} - (Cash Entry)',
                'date':cash.date,
                'supplier':cash.supplier.name if cash.supplier else '', 
                'party':cash.transaction,
                'qty':'1',
                'rate':cash.amount,
                'total_amount':cash.amount,
                'description':cash.description,
                'balance':cash.party_balance,
            })
        context = {
            'suppliers':suppliers,
            'date_from':date_from,
            'date_to':date_to,
            'ledgers':ledgers,
            'supplier':supplier if supplier else ''
            }
        return render(request,'supplier_ledger/supplier_ledger.html',context)
            
            
        