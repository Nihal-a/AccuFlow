import datetime
import json
from django.shortcuts import render, redirect, get_object_or_404
from core.models import StockTransfers, Godowns
from django.views import View
from django.http import JsonResponse
from core.views import getClient

class StockTransferView(View):
    def get(self, request):
        client = getClient(request.user)
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')

        transfers = StockTransfers.objects.filter(is_active=True, client=client).order_by('-id')

        if from_date:
            transfers = transfers.filter(date__gte=from_date)
        if to_date:
            transfers = transfers.filter(date__lte=to_date)

        transferData = []
        for transfer in transfers:
            transferData.append({
                'id': transfer.id,
                'transfer_no': transfer.transfer_no,
                'godown_from': transfer.transfer_from.name if transfer.transfer_from else '',
                'godown_to': transfer.transfer_to.name if transfer.transfer_to else '',
                'date': str(transfer.date),
                'qty': transfer.qty,
                'description': transfer.description if transfer.description else '',
            })
            
        godowns = Godowns.objects.filter(is_active=True, client=client)
        context = {
            'godowns': godowns,
            'last_transfer_no': getLastTransferNo(client=client),
            'transfers': transferData,
            'from_date': from_date,
            'to_date': to_date,
        }
        return render(request, 'stock_transfer/stock_transfer.html', context)

class StockTransferAddView(View):
    def post(self, request):
        client = getClient(request.user)
        dates = request.POST.getlist('dates')
        godown_from_ids = request.POST.getlist('godowns_from')
        godown_to_ids = request.POST.getlist('godowns_to')
        qtys = request.POST.getlist('qtys')
        descriptions = request.POST.getlist('descriptions')
        request_transfer_no = request.POST.get('transfer_no')

        if dates:
            for i in range(len(dates)):
                if not (godown_from_ids[i] and godown_to_ids[i] and qtys[i]):
                    continue
                    
                godown_from = get_object_or_404(Godowns, id=godown_from_ids[i], client=client)
                godown_to = get_object_or_404(Godowns, id=godown_to_ids[i], client=client)
                
                from decimal import Decimal
                qty = Decimal(str(qtys[i]))
                
                # Update balances
                godown_from.qty -= qty
                godown_from.save()
                
                godown_to.qty += qty
                godown_to.save()
                
                # Create transfer record
                StockTransfers.objects.create(
                    transfer_no=request_transfer_no,
                    transfer_from=godown_from,
                    transfer_to=godown_to,
                    date=dates[i],
                    qty=qty,
                    description=descriptions[i],
                    client=client,
                    is_active=True
                )
                
        return redirect('stocktransfer')

def get_transfer_no_api(request):
    client = getClient(request.user)
    try:
        new_no = getLastTransferNo(client)
    except:
        new_no = 1
    return JsonResponse({'transfer_no': new_no})

def getLastTransferNo(client):
    try:
        last_transfer = StockTransfers.objects.filter(is_active=True, client=client).order_by('-id').first()
        if last_transfer and last_transfer.transfer_no and last_transfer.transfer_no.isdigit():
            return int(last_transfer.transfer_no) + 1
        return 1
    except Exception as e:
        print(f"Error getting last transfer no: {e}")
        return 1
