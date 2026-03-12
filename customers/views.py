from django.shortcuts import render,redirect, get_object_or_404
from core.models import Customers, Sales, Purchases, NSDs, Cashs, Suppliers
from django.views import View
from django.views.decorators.http import require_POST
from django.db.models import Sum, Q
from datetime import datetime
from decimal import Decimal

from core.views import getClient
from core.authorization import get_object_for_user

class CustomerView(View):
    def get(self,request):
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'customer/customers.html',{'customers':customers})


class AddCustomerView(View):
    def get(self,request):
        return render(request,'customer/create.html')
    
    def post(self,request):
        client = getClient(request.user)
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        try:
            open_credit = Decimal(str(request.POST.get('open_credit', 0)))
            open_debit = Decimal(str(request.POST.get('open_debit', 0)))
            otc_credit = Decimal(str(request.POST.get('otc_credit', 0)))
            otc_debit = Decimal(str(request.POST.get('otc_debit', 0)))
        except Exception:
            return redirect('customers')
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        open_balance = open_debit - open_credit
        otc_balance = otc_debit - otc_credit
        balance = otc_balance + open_balance
        credit = Decimal('0.0000')
        debit = Decimal('0.0000')
        if balance > 0:
            debit = balance
            credit = Decimal('0.0000') 
        elif balance < 0:
            credit = -balance 
            debit = 0
        customer = Customers.objects.create(
            name=name,
            phone=phone,
            address=address,
            open_credit=open_credit,
            open_debit=open_debit,
            otc_credit=otc_credit,
            otc_debit=otc_debit,
            customerId=last_customer_id(client=client),
            client=client,
            open_balance = open_balance,
            otc_balance = otc_balance,
            balance = balance,
            credit = credit,
            debit = debit
        )
        if wa:
            customer.country_code = country_code
            customer.wa = wa
            customer.save()
        return redirect('customers')

class DeleteCustomerView(View):
    def post(self, request, customer_id):
        # Authorization: Ensure customer belongs to user's client (or user is superuser)
        customer = get_object_for_user(Customers, request.user, id=customer_id)
        customer.is_active = False 
        customer.save()
        return redirect('customers')
 

class UpdateCustomerView(View): 
    def get(self, request, customer_id):
        # Authorization: Ensure customer belongs to user's client (or user is superuser)
        customer = get_object_for_user(Customers, request.user, id=customer_id)
        return render(request, 'customer/update.html', {'customer': customer})

    def post(self, request, customer_id):
        # Authorization: Ensure customer belongs to user's client (or user is superuser)
        customer = get_object_for_user(Customers, request.user, id=customer_id)
        customer.name = request.POST.get('name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        try:
            customer.open_credit = Decimal(str(request.POST.get('open_credit', 0)))
            customer.open_debit = Decimal(str(request.POST.get('open_debit', 0)))
            customer.otc_credit = Decimal(str(request.POST.get('otc_credit', 0)))
            customer.otc_debit = Decimal(str(request.POST.get('otc_debit', 0)))
        except Exception:
            return redirect('customers')
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        
        customer.balance -= (customer.otc_balance + customer.open_balance)
        customer.credit = Decimal('0.0000')
        customer.debit = Decimal('0.0000')
        
        open_balance = customer.open_debit - customer.open_credit
        otc_balance = customer.otc_debit - customer.otc_credit
        
        customer.open_balance = open_balance
        customer.otc_balance = otc_balance
        customer.balance += (otc_balance + open_balance)
        
        total_bal = otc_balance + open_balance
        if total_bal > 0:
            customer.debit = total_bal
            customer.credit = Decimal('0.0000')
        elif total_bal < 0:
            customer.credit = -total_bal
            customer.debit = Decimal('0.0000')
        if wa:
            customer.country_code = country_code
            customer.wa = wa
        if customer.customerId is None:
            customer.customerId = last_customer_id(client=getClient(request.user))
        customer.save()
        return redirect('customers')

class CustomerDetailView(View):
    def get(self, request, customer_id):
        # Authorization: Ensure customer belongs to user's client (or user is superuser)
        customer = get_object_for_user(Customers, request.user, id=customer_id)
        return render(request, 'customer/view.html', {'customer': customer})
    
    
def last_customer_id(client):
    last_customer = Customers.objects.filter(is_active=True,client=client).order_by('customerId').last() 
    if last_customer and last_customer.customerId != None:
        prefix, num = last_customer.customerId.split('-')
        new_customer_id = f"{prefix}-{int(num) + 1}"
    else: 
        
        new_customer_id = 'C-1'
    return new_customer_id

class CustomerLedgerView(View):
    def get(self, request):
        customers = Customers.objects.filter(is_active=True, client=getClient(request.user))
        return render(request, 'customer/customer_ledger.html', {'customers': customers, 'sort': 'Serial'})

    def post(self, request):
        customer_id = request.POST.get('customer')
        opening_flag = request.POST.get('opening')
        sort = request.POST.get('sort')
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        
        client = getClient(request.user)
        customers = Customers.objects.filter(is_active=True, client=client)

        context = {
            'customers': customers,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'sort': sort,
            'customer': '',
            'opening': opening_flag if opening_flag == 'on' else '',
            'ledgers': [],
            'credit_total': Decimal('0.0000'),
            'debit_total': Decimal('0.0000'),
            'total_balance': Decimal('0.0000'),
            'open_balance': Decimal('0.0000'),
        }

        if not customer_id:
            return render(request, 'customer/customer_ledger.html', context)

        customer = get_object_or_404(Customers, id=customer_id, is_active=True, client=client)
        context['customer'] = customer

        date_from = self.parse_date(date_from_str)
        date_to = self.parse_date(date_to_str)

        if date_from:
            opening_balance = self.calculate_opening_balance(customer, client, date_from)
        else:
            opening_balance = customer.open_debit - customer.open_credit
        
        context['open_balance'] = opening_balance

        ledger_items = []
        
        base_filter = Q(is_active=True, hold=False, client=client)
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        # Sales (Debit for Customer)
        sales = Sales.objects.filter(base_filter, date_filter, customer=customer).select_related('godown')
        for s in sales:
            desc = f"{s.godown.name}\n{s.description}" if sort != 'Detailed' else s.description
            ledger_items.append({
                'transaction_no': str(s.sale_no),
                'date': s.date,
                'type': 'SL',
                'description': desc,
                'qty': s.qty,
                'rate': s.amount,
                'credit': 0,
                'debit': s.total_amount,
                'created_at': s.created_at,
                'original_obj': s
            })

        # Purchases from Customer (Credit for Customer) - Rare but possible
        purchases = Purchases.objects.filter(base_filter, date_filter, customer=customer).select_related('godown')
        for p in purchases:
            desc = f"{p.godown.name}\n{p.description}" if sort != 'Remark' else p.description
            ledger_items.append({
                'transaction_no': str(p.purchase_no),
                'date': p.date,
                'type': 'PR',
                'description': desc,
                'qty': p.qty,
                'rate': p.amount,
                'credit': p.total_amount,
                'debit': 0,
                'created_at': p.created_at,
                'original_obj': p
            })

        # NSD Sender (Customer sends goods -> We receive -> Purchase -> Credit)
        sender_nsds = NSDs.objects.filter(base_filter, date_filter, sender_customer=customer)
        for n in sender_nsds:
            desc = f"{n.receiver.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.sell_rate, # or purchase rate? Sender -> Sell Amount? 
                # NSD Logic: Sender sells (Sell Rate), Receiver buys (Purchase Rate).
                # If Customer IS Sender, they are Selling to us/someone.
                # If they sell, they expect payment -> Credit (Liability for us).
                'credit': n.sell_amount,
                'debit': 0, 
                'created_at': n.created_at,
                'original_obj': n
            })

        # NSD Receiver (Customer receives goods -> We/Someone sent -> Sale -> Debit)
        receiver_nsds = NSDs.objects.filter(base_filter, date_filter, receiver_customer=customer)
        for n in receiver_nsds:
            desc = f"{n.sender.name}\n{n.description}" if sort != 'Remark' else n.description
            ledger_items.append({
                'transaction_no': str(n.nsd_no),
                'date': n.date,
                'type': 'NS',
                'description': desc,
                'qty': n.qty,
                'rate': n.purchase_rate, 
                'credit': 0,
                'debit': n.purchase_amount,
                'created_at': n.created_at,
                'original_obj': n
            })

        # Cash (Received from Customer -> Credit. Paid to Customer -> Debit)
        cashs = Cashs.objects.filter(base_filter, date_filter, customer=customer).select_related('cash_bank')
        for c in cashs:
            is_received = (c.transaction == 'Received')
            desc = c.cash_bank.name if sort != 'Remark' else c.description
            ledger_items.append({
                'transaction_no': str(c.cash_no),
                'date': c.date,
                'type': 'JL',
                'description': desc,
                'qty': '',
                'rate': c.amount,
                'credit': c.amount if is_received else Decimal('0.0000'), # Received reduces balance (Credit)
                'debit': c.amount if not is_received else Decimal('0.0000'), # Paid increases balance (Debit)
                'created_at': c.created_at,
                'original_obj': c
            })

        start_balance = 0
        if opening_flag != 'on':
             start_balance = opening_balance
             ledger_items.append({
                'transaction_no': 'Opening Balance',
                'date': customer.created_at.date() if customer.created_at else (date_from or datetime.min.date()),
                'type': 'OB',
                'description': '',
                'qty': '1',
                'rate': customer.open_balance,
                'credit': customer.open_credit,
                'debit': customer.open_debit,
                'balance': customer.open_balance, 
                'created_at': customer.created_at,
                'is_ob': True
             })
        
        ledger_items.sort(key=lambda x: (x['date'], x['created_at']))

        if sort == 'Serial':
             ledger_items.sort(key=lambda x: x['transaction_no'])

        running_val = start_balance
        credit_sum = Decimal('0.0000')
        debit_sum = Decimal('0.0000')
        
        final_ledgers = []
        
        for item in ledger_items:
            c_val = Decimal(str(item.get('credit') or 0))
            d_val = Decimal(str(item.get('debit') or 0))
            
            if item.get('type') == 'OB':
                item['balance'] = start_balance
            else:
                running_val += (d_val - c_val) # Debit - Credit for Customer Asset/Receivable logic
                item['balance'] = running_val
                
                credit_sum += c_val
                debit_sum += d_val
            
            final_ledgers.append(item)
            
        if opening_flag == 'on':
            context['open_balance'] = 0

        context['ledgers'] = final_ledgers
        context['credit_total'] = credit_sum
        context['debit_total'] = debit_sum
        context['total_balance'] = running_val
        
        return render(request, 'customer/customer_ledger.html', context)

    def parse_date(self, date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def calculate_opening_balance(self, customer, client, date_limit):
        base_filter = Q(is_active=True, hold=False, client=client, customer=customer, date__lt=date_limit)
        nsd_base = Q(is_active=True, hold=False, client=client, date__lt=date_limit)
        
        purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
        sender_sum = NSDs.objects.filter(nsd_base, sender_customer=customer).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
        receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=customer).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
        
        cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
        
        # Balance = Debit - Credit
        # Debit: Sales, NSD Receiver, Cash Paid
        # Credit: Purchases, NSD Sender, Cash Received
        
        transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
        
        static_ob = customer.open_debit - customer.open_credit
        
        return static_ob + transaction_balance