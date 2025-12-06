from django.shortcuts import render,redirect, get_object_or_404
from core.models import Customers
from django.views import View
from django.views.generic.edit import DeleteView

from core.views import getClient

class CustomerView(View):
    def get(self,request):
        customers = Customers.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'customer/customers.html',{'customers':customers})


class AddCustomerView(View):
    def get(self,request):
        return render(request,'customer/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        open_credit = request.POST.get('open_credit',0)
        open_debit = request.POST.get('open_debit',0)
        otc_credit = request.POST.get('otc_credit',0)
        otc_debit = request.POST.get('otc_debit',0)
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        open_balance = float(open_debit)-float(open_credit)
        otc_balance = float(otc_debit) - float(otc_credit)
        balance = otc_balance + open_balance
        credit = 0
        debit = 0
        if balance> 0:
            debit = balance
            credit = 0 
        elif balance< 0:
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
            customerId=last_customer_id(client=getClient(request.user)),
            client=getClient(request.user),
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
    def get(self, request, customer_id):
        customer = get_object_or_404(Customers, id=customer_id)
        customer.is_active = False 
        customer.save()
        return redirect('customers')
 

class UpdateCustomerView(View): 
    def get(self, request, customer_id):
        customer = get_object_or_404(Customers, id=customer_id)
        return render(request, 'customer/update.html', {'customer': customer})

    def post(self, request, customer_id):
        customer = get_object_or_404(Customers, id=customer_id)
        customer.name = request.POST.get('name')
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        customer.open_credit = request.POST.get('open_credit', 0)
        customer.open_debit = request.POST.get('open_debit', 0)
        customer.otc_credit = request.POST.get('otc_credit', 0)
        customer.otc_debit = request.POST.get('otc_debit', 0)
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        customer.balance -= (customer.otc_balance + customer.open_balance)
        customer.credit -= customer.credit
        customer.debit -= customer.debit
        open_balance = float(request.POST.get('open_debit', 0))-float(request.POST.get('open_credit', 0))
        otc_balance = float(request.POST.get('otc_debit', 0))-float(request.POST.get('otc_credit', 0))
        customer.open_balance = open_balance
        customer.otc_balance = otc_balance
        customer.balance += (otc_balance + open_balance)
        if (otc_balance + open_balance)> 0:
            customer.debit = (otc_balance + open_balance)
            customer.credit = 0
        elif (otc_balance + open_balance)< 0:
            customer.credit = -(otc_balance + open_balance)
            customer.debit = 0
        if wa:
            customer.country_code = country_code
            customer.wa = wa
        if customer.customerId is None:
            customer.customerId = last_customer_id(client=getClient(request.user))
        customer.save()
        return redirect('customers')
    
    
def last_customer_id(client):
    last_customer = Customers.objects.filter(is_active=True,client=client).order_by('customerId').last() 
    if last_customer and last_customer.customerId != None:
        prefix, num = last_customer.customerId.split('-')
        new_customer_id = f"{prefix}-{int(num) + 1}"
    else: 
        
        new_customer_id = 'C-1'
    return new_customer_id