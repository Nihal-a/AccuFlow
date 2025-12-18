import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import StockTransfers,Expenses,Godowns
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient

class StockTransferView(View):
    def get(self,request):
        stock_transfers = StockTransfers.objects.filter(hold=True,is_active=True,client=getClient(request.user))
        transferData = []
        for transfer in stock_transfers:
            transferData.append({
                'id':transfer.id,
                'transfer_no':transfer.transfer_no,
                'godown_from':transfer.transfer_from.name if transfer.transfer_from else '',
                'godown_from_id':transfer.transfer_from.id if transfer.transfer_from else '',
                'transfer_no':transfer.transfer_no,
                'godown_to':transfer.transfer_to.name if transfer.transfer_to else '',
                'godown_to_id':transfer.transfer_to.id if transfer.transfer_to else '',
                'date':str(transfer.date),
                'qty':transfer.qty,
                'description':transfer.description if transfer.description else '', 
            })
        godowns = Godowns.objects.filter(is_active=True,client=getClient(request.user))
        context = {
            'godowns':godowns,
            'last_commission_no':getLastTransferNo(client=getClient(request.user)),
        }
        return render(request,'stock_transfer/stock_transfer.html',context)
    
class StockTransferAddView(View):
    def post(self,request):
        dates = request.POST.getlist('dates')
        qtys = request.POST.getlist('qtys')
        expense_ids = request.POST.getlist('expenses')
        godown_ids = request.POST.getlist('godowns')
        commission_ids = request.POST.getlist('commission_ids') 
        count = 0
        for id in commission_ids:
            expense = get_object_or_404(Expenses, id=expense_ids[count]) if expense_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            godown.qty -= float(qtys[count])
            godown.save()
            commission = Commissions.objects.get(id=id)
            commission.godown_balance = godown.qty
            commission.expense = expense
            commission.godown = godown
            commission.date = dates[count]
            commission.qty = qtys[count]
            commission.amount = amounts[count]
            commission.total_amount = total_amounts[count]    
            commission.hold = False
            commission.client=getClient(request.user)
            commission.save()  
            count += 1
        return redirect('commission')


    
def getLastTransferNo(client):
    last_transfer_no = StockTransfers.objects.filter(is_active=True,client=client).order_by('-transfer_no').first() 
    
    if last_transfer_no and last_transfer_no.transfer_no_no.isdigit():
        new_transfer_no = int(last_transfer_no.transfer_no) + 1
    else:
        new_transfer_no = 1
    return new_transfer_no
