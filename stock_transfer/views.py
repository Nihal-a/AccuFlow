import datetime
import json
from django.utils.dateparse import parse_date
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

        if from_date and to_date:
            transfers = StockTransfers.objects.filter(
                is_active=True, 
                hold=False, 
                client=client,
                date__gte=from_date,
                date__lte=to_date
            ).order_by('-id')
        else:
            transfers = []

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
        held_transfers = StockTransfers.objects.filter(is_active=True, hold=True, client=client)
        held_transfer_data = []
        for transfer in held_transfers:
            held_transfer_data.append({
                'id': transfer.id,
                'transfer_no': transfer.transfer_no,
                'godown_from': transfer.transfer_from.name if transfer.transfer_from else '',
                'godown_from_id': transfer.transfer_from.id if transfer.transfer_from else '',
                'godown_to': transfer.transfer_to.name if transfer.transfer_to else '',
                'godown_to_id': transfer.transfer_to.id if transfer.transfer_to else '',
                'date': str(transfer.date),
                'qty': str(transfer.qty),
                'description': transfer.description if transfer.description else '',
            })

        context = {
            'godowns': godowns,
            'last_transfer_no': getLastTransferNo(client=client),
            'transfers': transferData,
            'held_transfers': held_transfer_data,
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

        transfer_ids = request.POST.getlist('transfer_ids')
        if dates:
            for i in range(len(dates)):
                if not (godown_from_ids[i] and godown_to_ids[i] and qtys[i]):
                    continue
                    
                godown_from = get_object_or_404(Godowns, id=godown_from_ids[i], client=client)
                godown_to = get_object_or_404(Godowns, id=godown_to_ids[i], client=client)
                
                from decimal import Decimal
                qty = Decimal(str(qtys[i]))
                
                # Check if it was a held transfer to approve
                if transfer_ids and len(transfer_ids) > i and transfer_ids[i]:
                    transfer = get_object_or_404(StockTransfers, id=transfer_ids[i], client=client)
                    if transfer.hold: # Only deduct stock balances if it was previously just held
                        godown_from.qty -= qty
                        godown_from.save()
                        
                        godown_to.qty += qty
                        godown_to.save()
                        
                        transfer.hold = False
                        transfer.save()
                else:    
                    # Update balances for new direct creation
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
                        hold=False,
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
        last_transfer = StockTransfers.objects.filter(is_active=True, hold=False, client=client).order_by('-id').first()
        if last_transfer and last_transfer.transfer_no and last_transfer.transfer_no.isdigit():
            return int(last_transfer.transfer_no) + 1
        return 1
    except Exception as e:
        print(f"Error getting last transfer no: {e}")
        return 1

from core.authorization import get_object_for_user

from decimal import Decimal

class StockTransferHoldView(View):
    def post(self, request):
        client = getClient(request.user)
        try:
            data = json.loads(request.body)
            transfer_no = data.get('transfer_no')
            date = data.get('date')
            godown_from_id = data.get('godown_from')
            godown_to_id = data.get('godown_to')
            qty = Decimal(str(data.get('qty', 0)))
            description = data.get('description')
            transfer_id = data.get('transfer_id')

            godown_from = get_object_for_user(Godowns, request.user, id=godown_from_id) if godown_from_id else None
            godown_to = get_object_for_user(Godowns, request.user, id=godown_to_id) if godown_to_id else None

            if transfer_id:
                # Update existing hold
                transfer = get_object_for_user(StockTransfers, request.user, id=transfer_id)
                
                # If editing a posted transfer, carefully reverse the old quantities FIRST
                if not transfer.hold:
                    # Refresh the old godowns directly from the database to avoid memory overlaps
                    old_from = get_object_or_404(Godowns, id=transfer.transfer_from.id)
                    old_to = get_object_or_404(Godowns, id=transfer.transfer_to.id)
                    
                    old_from.qty += transfer.qty
                    old_from.save()
                    
                    old_to.qty -= transfer.qty
                    old_to.save()

                transfer.transfer_no = transfer_no
                transfer.date = date
                transfer.transfer_from = godown_from
                transfer.transfer_to = godown_to
                transfer.qty = qty
                transfer.description = description
                transfer.save()
                
                # Re-apply quantities to the newly selected godowns if it's a posted transfer
                if not transfer.hold:
                    godown_from.refresh_from_db()
                    godown_from.qty -= qty
                    godown_from.save()
                    
                    godown_to.refresh_from_db()
                    godown_to.qty += qty
                    godown_to.save()
                    
                return JsonResponse({'status': 'success', 'transfer_id': transfer.id, 'hold': transfer.hold})
            
            # Create new hold
            transfer = StockTransfers.objects.create(
                transfer_no=transfer_no,
                date=date,
                transfer_from=godown_from,
                transfer_to=godown_to,
                qty=qty,
                description=description,
                hold=True,
                is_active=True,
                client=client
            )
            return JsonResponse({'status': 'success', 'transfer_id': transfer.id, 'hold': transfer.hold})

        except Exception as e:
            print(f"Error holding transfer: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def delete_transfer_api(request):
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            pk = data.get('id')
        else:
            pk = request.GET.get('id')
            
        if not pk:
            return JsonResponse({'status': 'error', 'message': 'No ID provided'}, status=400)
            
        transfer = get_object_for_user(StockTransfers, request.user, id=pk)
        
        # Only adjust balances if it's NOT a hold transfer or if we somehow need to reverse.
        # But generally, hold transfers haven't affected balances yet.
        if not transfer.hold:
            # Reverse balance logic if deleting an actual posted transfer...
            transfer.transfer_from.qty += transfer.qty
            transfer.transfer_from.save()
            transfer.transfer_to.qty -= transfer.qty
            transfer.transfer_to.save()
            
        transfer.is_active = False
        transfer.save()
        return JsonResponse({'status': 'success', 'message': 'Transfer deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting transfer: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def transfers_by_date(request):
    client = getClient(request.user)
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    transfersData = []

    if from_date and to_date:
        transfers = StockTransfers.objects.filter(
            is_active=True,
            hold=False,
            client=client,
            date__range=[parse_date(from_date), parse_date(to_date)]
        ).order_by('-id')

        for transfer in transfers:
            transfersData.append({
                'id': transfer.id,
                'transfer_no': transfer.transfer_no,
                'godown_from': transfer.transfer_from.name if transfer.transfer_from else '',
                'godown_from_id': transfer.transfer_from.id if transfer.transfer_from else '',
                'godown_to': transfer.transfer_to.name if transfer.transfer_to else '',
                'godown_to_id': transfer.transfer_to.id if transfer.transfer_to else '',
                'date': str(transfer.date),
                'qty': str(transfer.qty),
                'description': transfer.description if transfer.description else '',
            })
            
    return JsonResponse({'transfers': transfersData})

def godown_balances_api(request):
    client = getClient(request.user)
    godowns = Godowns.objects.filter(is_active=True, client=client)
    data = {str(g.id): str(g.qty) for g in godowns}
    return JsonResponse(data)
