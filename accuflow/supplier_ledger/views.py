from django.shortcuts import render,redirect, get_object_or_404
from core.models import Suppliers
from django.views import View
from core.views import getClient
from core.models import *
from datetime import datetime
from django.utils import timezone


class SupplierLedgerView(View):
    def get(self,request):
        suppliers = Suppliers.objects.filter(is_active=True,client = getClient(request.user))
        return render(request,'supplier_ledger/supplier_ledger.html',{'suppliers':suppliers})

    def post(self,request): 
        supplier = request.POST.get('supplier')
        opening = request.POST.get('opening')
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
        credit_total = 0
        debit_total = 0
        if supplier:
            supplier = Suppliers.objects.get(id=supplier)
            if opening != 'on': 
                ledgers.append({
                    'transaction_no':'Opening Balance',
                    'date':supplier.created_at,
                    'supplier':supplier if supplier else '',
                    'type':'OB',
                    'qty':'1',
                    'rate':supplier.open_balance,
                    'credit':supplier.open_credit,
                    'debit':supplier.open_debit,
                    'balance':supplier.open_balance, 
                    'created_at':supplier.created_at,
                })
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
                'transaction_no':f'{purchase.purchase_no}',
                'date':purchase.date,
                'supplier':purchase.supplier if purchase.supplier else '',
                'type':'PR',
                'qty':purchase.qty,
                'rate':purchase.amount,
                'credit':purchase.total_amount,
                'debit':'0',
                'balance':purchase.seller_balance,
                'created_at':purchase.created_at,
            })
            credit_total += purchase.total_amount
        for sale in sales:
            ledgers.append({
                'transaction_no':f'{sale.sale_no}',
                'date':sale.date,
                'supplier':sale.supplier if sale.supplier else '',
                'type':'SL',
                'qty':sale.qty,
                'rate':sale.amount,
                'credit':'0',
                'debit':sale.total_amount,
                'balance':sale.seller_balance,
                'created_at':sale.created_at,
            })
            debit_total += sale.total_amount
        for nsd in sender_nsds:
            ledgers.append({
                'transaction_no':f'{nsd.nsd_no}',
                'date':nsd.date,
                'supplier':nsd.sender_supplier if nsd.sender_supplier else '',
                'type':'NS',
                'qty':nsd.qty,
                'rate':nsd.sell_rate,
                'credit':nsd.sell_amount,
                'debit':'0',
                'balance':nsd.sender_balance,
                'created_at':nsd.created_at,
            })
            credit_total += nsd.sell_amount
        for nsd in receiver_nsds:
            ledgers.append({
                'transaction_no':f'{nsd.nsd_no}',
                'date':nsd.date,
                'supplier':nsd.sender_supplier if nsd.sender_supplier else '',
                'type':'NS',
                'qty':nsd.qty,
                'rate':nsd.purchase_rate,
                'debit':nsd.purchase_amount,
                'credit':'0',
                'balance':nsd.receiver_balance,
                'created_at':nsd.created_at,
            })
            debit_total += nsd.purchase_amount
        for cash in cashs:
            ledgers.append({
                'transaction_no':f'{cash.cash_no}',
                'date':cash.date,
                'supplier':cash.supplier if cash.supplier else '', 
                'type':'JL',
                'qty':'',
                'rate':cash.amount,
                'credit':cash.amount if cash.transaction == 'Received' else '',
                'debit':cash.amount if cash.transaction == 'Paid' else '',
                'balance':cash.party_balance,
                'created_at':cash.created_at,
            }) 
            if cash.transaction == 'Received':
                credit_total += cash.amount
            else:
                debit_total += cash.amount
        for entry in ledgers:

            d = entry["created_at"]
            if not isinstance(d, datetime):
                d = datetime.combine(d, datetime.min.time())
            entry["created_at"] = timezone.make_aware(d) if timezone.is_naive(d) else d

            date_val = entry["date"]
            if not isinstance(date_val, datetime):
                date_val = datetime.combine(date_val, datetime.min.time())
            entry["date"] = timezone.make_aware(date_val) if timezone.is_naive(date_val) else date_val


        ledgers = sorted(ledgers, key=lambda x: (x['date'], x['created_at']))
        total_balance = ledgers[len(ledgers)-1]['balance'] if ledgers else 0
        opening_balance = 0
        if date_from and supplier:
            prev_sales = Sales.objects.filter(
                is_active=True, hold=False, supplier=supplier, client=getClient(request.user), date__lt=date_from
            )
            prev_purchases = Purchases.objects.filter(
                is_active=True, hold=False, supplier=supplier, client=getClient(request.user), date__lt=date_from
            )
            prev_sender = NSDs.objects.filter(
                is_active=True, hold=False, sender_supplier=supplier, client=getClient(request.user), date__lt=date_from
            )
            prev_receiver = NSDs.objects.filter(
                is_active=True, hold=False, receiver_supplier=supplier, client=getClient(request.user), date__lt=date_from
            )
            prev_cash = Cashs.objects.filter(
                is_active=True, hold=False, supplier=supplier, client=getClient(request.user), date__lt=date_from
            )

            for p in prev_purchases:
                opening_balance += p.total_amount

            for s in prev_sales:
                opening_balance -= s.total_amount

            for ns in prev_sender:
                opening_balance += ns.sell_amount

            for nr in prev_receiver:
                opening_balance -= nr.purchase_amount

            for c in prev_cash:
                if c.transaction == "Received":
                    opening_balance += c.amount
                else:
                    opening_balance -= c.amount
        
        context = {
            'suppliers':suppliers,
            'date_from':date_from,
            'date_to':date_to,
            'ledgers':ledgers,
            'supplier':supplier if supplier else '',
            'opening':opening if opening == 'on' else '',
            'credit_total':credit_total,
            'debit_total':debit_total,
            'total_balance':total_balance,
            'open_balance':opening_balance,
            }
        return render(request,'supplier_ledger/supplier_ledger.html',context)
            
            
        