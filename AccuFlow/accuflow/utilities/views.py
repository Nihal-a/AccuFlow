
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from datetime import datetime
from core.models import Godowns, Sales, Suppliers, NSDs
from core.views import getClient
from django.http import HttpResponse
import openpyxl
from io import BytesIO

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
        date_from_str = request.POST.get('date_from')
        date_to_str = request.POST.get('date_to')
        party_id = request.POST.get('party_id')
        is_nsd = request.POST.get('is_nsd') == 'on'

        godowns = Godowns.objects.filter(is_active=True, client=client)
        suppliers = Suppliers.objects.filter(is_active=True, client=client)

        transactions = []
        
        if date_from_str and date_to_str and party_id:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
                
                if is_nsd:
                    nsds = NSDs.objects.filter(
                        client=client,
                        is_active=True,
                        date__range=[date_from, date_to],
                        sender_supplier_id=party_id
                    )
                    for n in nsds:
                        transactions.append({
                            'slno': n.nsd_no, 
                            'description': n.description,
                            'qty': n.qty,
                            'date': n.date
                        })
                else:
                    sales = Sales.objects.filter(
                        client=client,
                        is_active=True,
                        date__range=[date_from, date_to],
                         godown_id=party_id
                    )
                    for s in sales:
                        transactions.append({
                            'slno': s.sale_no,
                            'description': s.description,
                            'qty': s.qty,
                            'date': s.date
                        })
                        
            except ValueError:
                pass
        
        if request.POST.get('export') == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Address View Report"
            
            # Header
            headers = ["Sl No", "Date", "Description", "Qty"]
            ws.append(headers)
            
            for item in transactions:
                # Date format
                d_str = item['date'].strftime("%d-%m-%Y") if item['date'] else ""
                row = [
                    item['slno'],
                    d_str,
                    item['description'],
                    item['qty']
                ]
                ws.append(row)
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="address_view_report.xlsx"'
            return response

        return render(request, 'stock_view/address_view.html', {
            'godowns': godowns,
            'suppliers': suppliers,
            'transactions': transactions,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'selected_party': party_id,
            'is_nsd': is_nsd
        })
