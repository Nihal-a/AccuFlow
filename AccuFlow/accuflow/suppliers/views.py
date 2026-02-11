from django.shortcuts import render,redirect, get_object_or_404
from core.models import Suppliers
from django.views import View
from decimal import Decimal
from django.views.generic.edit import DeleteView
from core.views import getClient
from core.authorization import get_object_for_user

class SupplierView(View):
    def get(self,request):
        suppliers = Suppliers.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'supplier/suppliers.html',{'suppliers':suppliers})


class AddSupplierView(View):
    def get(self,request):
        return render(request,'supplier/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        open_credit = Decimal(str(request.POST.get('open_credit', 0)))
        open_debit = Decimal(str(request.POST.get('open_debit', 0)))
        otc_credit = Decimal(str(request.POST.get('otc_credit', 0)))
        otc_debit = Decimal(str(request.POST.get('otc_debit', 0)))
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
            debit = Decimal('0.0000')
        supplier = Suppliers.objects.create(
            name=name,
            phone=phone,
            address=address,
            open_credit=open_credit,
            open_debit=open_debit,
            otc_credit=otc_credit,
            otc_debit=otc_debit,
            supplierId=new_supplier_id(client=getClient(request.user)),
            client=getClient(request.user),
            open_balance = open_balance,
            otc_balance = otc_balance,
            balance = balance,
            credit = credit,
            debit = debit
        )
        if wa:
            supplier.country_code = country_code
            supplier.wa = wa
            supplier.save()
        return redirect('suppliers')

class DeleteSupplierView(View):
    def get(self, request, supplier_id):
        # Authorization: Ensure supplier belongs to user's client (or user is superuser)
        supplier = get_object_for_user(Suppliers, request.user, id=supplier_id)
        supplier.is_active = False 
        supplier.save()
        return redirect('suppliers')
 

class UpdateSupplierView(View):
    def get(self, request, supplier_id):
        # Authorization: Ensure supplier belongs to user's client (or user is superuser)
        supplier = get_object_for_user(Suppliers, request.user, id=supplier_id)
        return render(request, 'supplier/update.html', {'supplier': supplier})

    def post(self, request, supplier_id):
        # Authorization: Ensure supplier belongs to user's client (or user is superuser)
        supplier = get_object_for_user(Suppliers, request.user, id=supplier_id)
        supplier.name = request.POST.get('name')
        supplier.phone = request.POST.get('phone')
        supplier.address = request.POST.get('address')
        supplier.open_credit = Decimal(str(request.POST.get('open_credit', 0)))
        supplier.open_debit = Decimal(str(request.POST.get('open_debit', 0)))
        customer_otc_credit = Decimal(str(request.POST.get('otc_credit', 0))) # Variable name fix if needed, but the field is otc_credit
        supplier.otc_credit = Decimal(str(request.POST.get('otc_credit', 0)))
        supplier.otc_debit = Decimal(str(request.POST.get('otc_debit', 0)))
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        
        supplier.balance -= (supplier.otc_balance + supplier.open_balance)
        supplier.credit = Decimal('0.0000')
        supplier.debit = Decimal('0.0000')
        
        open_balance = supplier.open_debit - supplier.open_credit
        otc_balance = supplier.otc_debit - supplier.otc_credit
        
        supplier.open_balance = open_balance
        supplier.otc_balance = otc_balance
        supplier.balance += (otc_balance + open_balance)
        
        total_bal = otc_balance + open_balance
        if total_bal > 0:
            supplier.debit = total_bal
            supplier.credit = Decimal('0.0000')
        elif total_bal < 0:
            supplier.credit = -total_bal
            supplier.debit = Decimal('0.0000')
        if wa:
            supplier.country_code = country_code
            supplier.wa = wa
        if supplier.supplierId is None:
            supplier.supplierId = new_supplier_id(client=getClient(request.user))
        supplier.save()
        return redirect('suppliers') 
     
    
def new_supplier_id(client):
    last_supplier = Suppliers.objects.filter(is_active=True,client=client).order_by('supplierId').last() 
    if last_supplier and last_supplier.supplierId != None:
        prefix, num = last_supplier.supplierId.split('-')
        new_supplier_id = f"{prefix}-{int(num) + 1}"
    else: 
        new_supplier_id = 'S-1'
    print("New Supplier ID:", new_supplier_id) 
    return new_supplier_id