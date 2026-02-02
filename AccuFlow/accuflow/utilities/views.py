
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from datetime import datetime
from core.models import Godowns, Sales, Suppliers, NSDs
from core.views import getClient

class AddressView(View):
    def get(self, request):
        client = getClient(request.user)
        godowns = Godowns.objects.filter(is_active=True, client=client)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)
        return render(request, 'stock_view/address_view.html', {
            'godowns': godowns,
            'suppliers': suppliers
        })

    def post(self, request):
        client = getClient(request.user)
        date_str = request.POST.get('date')
        party_id = request.POST.get('party_id')
        is_nsd = request.POST.get('is_nsd') == 'on'

        godowns = Godowns.objects.filter(is_active=True, client=client)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)

        transactions = []
        
        if date_str and party_id:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if is_nsd:
                    nsds = NSDs.objects.filter(
                        client=client,
                        is_active=True,
                        date=date_obj,
                        sender_supplier_id=party_id
                    )
                    for n in nsds:
                        transactions.append({
                            'slno': n.nsd_no, 
                            'description': n.description,
                            'qty': n.qty
                        })
                else:
                    sales = Sales.objects.filter(
                        client=client,
                         is_active=True,
                         date=date_obj,
                         godown_id=party_id
                    )
                    for s in sales:
                        transactions.append({
                            'slno': s.sale_no,
                            'description': s.description,
                            'qty': s.qty
                        })
                        
            except ValueError:
                pass

        return render(request, 'stock_view/address_view.html', {
            'godowns': godowns,
            'suppliers': suppliers,
            'transactions': transactions,
            'selected_date': date_str,
            'selected_party': party_id,
            'is_nsd': is_nsd
        })
