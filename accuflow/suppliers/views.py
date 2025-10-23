from django.shortcuts import render,redirect, get_object_or_404
from core.models import Suppliers
from django.views import View
from django.views.generic.edit import DeleteView

class SupplierView(View):
    def get(self,request):
        suppliers = Suppliers.objects.filter(is_active=True)
        return render(request,'supplier/suppliers.html',{'suppliers':suppliers})


class AddSupplierView(View):
    def get(self,request):
        return render(request,'supplier/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        open_credit = request.POST.get('open_credit',0)
        open_debit = request.POST.get('open_debit',0)
        otc_credit = request.POST.get('otc_credit',0)
        otc_debit = request.POST.get('otc_debit',0)
        
        Suppliers.objects.create(
            name=name,
            phone=phone,
            address=address,
            open_credit=open_credit,
            open_debit=open_debit,
            otc_credit=otc_credit,
            otc_debit=otc_debit
        )
        return redirect('suppliers')

class DeleteSupplierView(View):
    def get(self, request, supplier_id):
        supplier = get_object_or_404(Suppliers, id=supplier_id)
        supplier.is_active = False 
        supplier.save()
        return redirect('suppliers')
 

class UpdateSupplierView(View):
    def get(self, request, supplier_id):
        supplier = get_object_or_404(Suppliers, id=supplier_id)
        return render(request, 'supplier/update.html', {'supplier': supplier})

    def post(self, request, supplier_id):
        supplier = get_object_or_404(Suppliers, id=supplier_id)
        supplier.name = request.POST.get('name')
        supplier.phone = request.POST.get('phone')
        supplier.address = request.POST.get('address')
        supplier.open_credit = request.POST.get('open_credit', 0)
        supplier.open_debit = request.POST.get('open_debit', 0)
        supplier.otc_credit = request.POST.get('otc_credit', 0)
        supplier.otc_debit = request.POST.get('otc_debit', 0)
        supplier.save()
        return redirect('suppliers')