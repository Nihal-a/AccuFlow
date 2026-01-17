from django.shortcuts import render,redirect, get_object_or_404
from core.models import Godowns, Purchases, Sales, Commissions, StockTransfers
from django.views import View
from django.views.generic.edit import DeleteView
from django.db.models import Sum, Q 
from datetime import datetime

from core.views import getClient


class GodownView(View):
    def get(self,request):
        godown = Godowns.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'godown/godown.html',{'godowns':godown})


class AddGodownView(View):
    def get(self,request):
        return render(request,'godown/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        open_credit = request.POST.get('open_credit',0)
        open_debit = request.POST.get('open_debit',0)
        otc_credit = request.POST.get('otc_credit',0)
        otc_debit = request.POST.get('otc_debit',0)
        open_balance = float(open_debit)-float(open_credit)
        otc_balance = float(otc_debit) - float(otc_credit)
        balance = otc_balance + open_balance
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        
        credit = 0
        debit = 0
        if balance> 0:
            debit = balance
            credit = 0 
        elif balance< 0:
            credit = -balance 
            debit = 0
        godown = Godowns.objects.create(
            name=name,
            phone=phone,
            address=address,
            open_credit=open_credit,
            open_debit=open_debit,
            otc_credit=otc_credit,
            otc_debit=otc_debit,
            godownId=new_godown_id(client=getClient(request.user)),
            client=getClient(request.user),
            open_balance = open_balance,
            otc_balance = otc_balance,
            balance = balance,
            credit = credit,
            debit = debit
        )
        if wa:
            godown.country_code = country_code
            godown.wa = wa
            godown.save()
        return redirect('godown')

class DeleteGodownView(View):
    def get(self, request, godown_id):
        godown = get_object_or_404(Godowns, id=godown_id)
        godown.is_active = False 
        godown.save()
        return redirect('godown')
 

class UpdateGodownView(View):
    def get(self, request, godown_id): 
        godown = get_object_or_404(Godowns, id=godown_id)
        return render(request, 'godown/update.html', {'godown': godown})

    def post(self, request, godown_id):
        godown = get_object_or_404(Godowns, id=godown_id)
        godown.name = request.POST.get('name')
        godown.phone = request.POST.get('phone')
        godown.address = request.POST.get('address')
        godown.open_credit = request.POST.get('open_credit', 0)
        godown.open_debit = request.POST.get('open_debit', 0)
        godown.otc_credit = request.POST.get('otc_credit', 0)
        godown.otc_debit = request.POST.get('otc_debit', 0)
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        godown.client = getClient(request.user)
        godown.balance -= (godown.otc_balance + godown.open_balance)
        godown.credit -= godown.credit
        godown.debit -= godown.debit
        open_balance = float(request.POST.get('open_debit', 0))-float(request.POST.get('open_credit', 0))
        otc_balance = float(request.POST.get('otc_debit', 0))-float(request.POST.get('otc_credit', 0))
        godown.open_balance = open_balance
        godown.otc_balance = otc_balance
        godown.balance += (otc_balance + open_balance)
        if (otc_balance + open_balance)> 0:
            godown.debit = (otc_balance + open_balance)
            godown.credit = 0
        elif (otc_balance + open_balance)< 0:
            godown.credit = -(otc_balance + open_balance)
            godown.debit = 0
        if wa:
            godown.country_code = country_code
            godown.wa = wa
        if godown.godownId is None:
            godown.godownId = new_godown_id(client=getClient(request.user)) 
        godown.save()
        return redirect('godown')
    
    
def new_godown_id(client):
    last_godown = Godowns.objects.filter(is_active=True,client=client).order_by('godownId').last() 
    if last_godown and last_godown.godownId != None:
        prefix, num = last_godown.godownId.split('-')
        new_godown_id = f"{prefix}-{int(num) + 1}"
    else: 
        new_godown_id = 'G-1'
    return str(new_godown_id)

class GodownLedgerView(View):
    def get(self, request):
        godowns = Godowns.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'godown/godown_ledger.html', {'godowns': godowns, 'sort': 'Serial'})

    def post(self, request):
        godown_id = request.POST.get('godown')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        godowns = Godowns.objects.filter(is_active=True, client=client)

        context = {
            'godowns': godowns,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'godown': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'in_total': 0,
            'out_total': 0,
            'total_balance': 0,
            'open_balance': 0,
        }

        if not godown_id:
            return render(request, 'godown/godown_ledger.html', context)

        godown = get_object_or_404(Godowns, id=godown_id)
        context['godown'] = godown

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_stock(godown, client, date_from)
        else:
            opening_balance = 0 # No field for opening Qty
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client, godown=godown)
        transfer_filter_from = Q(is_active=True, hold=False, client=client, transfer_from=godown)
        transfer_filter_to = Q(is_active=True, hold=False, client=client, transfer_to=godown)

        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        # Purchases (In Qty)
        purchases = Purchases.objects.filter(base_filter, date_filter)
        for p in purchases:
            desc = p.description if sort != 'Detailed' else p.description
            ledger_items.append({
                'transaction_no': str(p.purchase_no),
                'date': p.date,
                'type': 'Purchase',
                'description': desc,
                'in_qty': p.qty,
                'out_qty': 0,
                'created_at': p.created_at,
                'original_obj': p
            })
            
        # Sales (Out Qty)
        sales = Sales.objects.filter(base_filter, date_filter)
        for s in sales:
            desc = s.description if sort != 'Detailed' else s.description
            ledger_items.append({
                'transaction_no': str(s.sale_no),
                'date': s.date,
                'type': 'Sale',
                'description': desc,
                'in_qty': 0,
                'out_qty': s.qty,
                'created_at': s.created_at,
                'original_obj': s
            })
            
        # Commissions (Out Qty)
        commissions = Commissions.objects.filter(base_filter, date_filter)
        for c in commissions:
            desc = c.description if sort != 'Detailed' else c.description
            ledger_items.append({
                'transaction_no': str(c.commission_no),
                'date': c.date,
                'type': 'Commission',
                'description': desc,
                'in_qty': 0,
                'out_qty': c.qty,
                'created_at': c.created_at,
                'original_obj': c
            })

        # Stock Transfers OUT (Out Qty)
        transfers_out = StockTransfers.objects.filter(transfer_filter_from, date_filter)
        for t in transfers_out:
            desc = f"To: {t.transfer_to.name if t.transfer_to else ''} - {t.description}"
            ledger_items.append({
                'transaction_no': str(t.transfer_no),
                'date': t.date,
                'type': 'Transfer Out',
                'description': desc,
                'in_qty': 0,
                'out_qty': t.qty,
                'created_at': t.created_at,
                'original_obj': t
            })

        # Stock Transfers IN (In Qty)
        transfers_in = StockTransfers.objects.filter(transfer_filter_to, date_filter)
        for t in transfers_in:
            desc = f"From: {t.transfer_from.name if t.transfer_from else ''} - {t.description}"
            ledger_items.append({
                'transaction_no': str(t.transfer_no),
                'date': t.date,
                'type': 'Transfer In',
                'description': desc,
                'in_qty': t.qty,
                'out_qty': 0,
                'created_at': t.created_at,
                'original_obj': t
            })


        start_balance = 0
        if opening_flag != 'on':
             start_balance = opening_balance
             ledger_items.append({
                'transaction_no': 'Opening Stock',
                'date': godown.created_at.date() if godown.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'in_qty': '',
                'out_qty': '',
                'balance': start_balance, 
                'created_at': godown.created_at,
                'is_ob': True
             })
        
        ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

        running_val = start_balance
        in_sum = 0
        out_sum = 0
        
        final_ledgers = []
        
        for item in ledger_items:
            in_q = float(item.get('in_qty') or 0)
            out_q = float(item.get('out_qty') or 0)
            
            if item.get('type') == 'OB':
                item['balance'] = start_balance
            else:
                running_val += (in_q - out_q)
                item['balance'] = running_val
                
                in_sum += in_q
                out_sum += out_q
            
            final_ledgers.append(item)
            
        if opening_flag == 'on':
            context['open_balance'] = 0

        context['ledgers'] = final_ledgers
        context['in_total'] = in_sum
        context['out_total'] = out_sum
        context['total_balance'] = running_val
        
        return render(request, 'godown/godown_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_stock(self, godown, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, godown=godown, date__lt=date_limit)
        transfer_filter_from = Q(is_active=True, hold=False, client=client, transfer_from=godown, date__lt=date_limit)
        transfer_filter_to = Q(is_active=True, hold=False, client=client, transfer_to=godown, date__lt=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or 0
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or 0
        commission_sum = Commissions.objects.filter(base_filter).aggregate(s=Sum('qty'))['s'] or 0

        transfers_in_sum = StockTransfers.objects.filter(transfer_filter_to).aggregate(s=Sum('qty'))['s'] or 0
        transfers_out_sum = StockTransfers.objects.filter(transfer_filter_from).aggregate(s=Sum('qty'))['s'] or 0
        
        # Stock = In - Out
        stock_balance = (purchases_sum + transfers_in_sum) - (sales_sum + commission_sum + transfers_out_sum)
        
        return stock_balance