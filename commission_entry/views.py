from django.views.decorators.http import require_POST
from django.db import transaction
import json
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Commissions,Expenses,Godowns
from django.views import View
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from core.views import getClient
from core.authorization import get_object_for_user
from core.utils import validate_positive_decimal

@method_decorator(never_cache, name='dispatch')
class CommissionEntryView(View):
    def get(self,request):
        client = getClient(request.user)
        commissions = Commissions.objects.filter(hold=True,is_active=True,client=client).select_related('expense', 'godown')
        commissionData = []
        for commission in commissions:
            commissionData.append({
                'id':commission.id,
                'commission_no':commission.commission_no,
                'expense':commission.expense.category if commission.expense else '',
                'expense_id':commission.expense.id if commission.expense else '',
                'godown':commission.godown.name if commission.godown else '',
                'godown_id':commission.godown.id if commission.godown else '',
                'date':str(commission.date),
                'qty':commission.qty,
                'amount':commission.amount,
                'total_amount':commission.total_amount,
                'description':commission.description if commission.description else '', 
            })
        expenses = Expenses.objects.filter(is_active=True,client=client)
        godowns = Godowns.objects.filter(is_active=True,client=client)
        expensesData = []
        for expense in expenses:
            expensesData.append({
                'id':expense.id,
                'name':expense.category,
                'expenseId':expense.expenseId,
            })
        context = {
            'commissions':commissionData,
            'expenses':expensesData,
            'godowns':godowns,
            'last_commission_no':getLastCommissionNo(client=client),
        }
        return render(request,'commission_entry/commission_entry.html',context)
    
    

@method_decorator(never_cache, name='dispatch')
class CommissionAddView(View):
    @transaction.atomic
    def post(self,request):
        dates = request.POST.getlist('dates')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        expense_ids = request.POST.getlist('expenses')
        godown_ids = request.POST.getlist('godowns')
        commission_ids = request.POST.getlist('commission_ids') 
        count = 0
        for id in commission_ids:
            expense = get_object_for_user(Expenses, request.user, id=expense_ids[count]) if expense_ids[count] else None
            godown = get_object_for_user(Godowns, request.user, id=godown_ids[count]) if godown_ids[count] else None
            
            # Validation
            try:
                qty_val = Decimal(str(qtys[count] or 0))
                amount_val = Decimal(str(amounts[count] or 0))
                total_amount_val = (qty_val * amount_val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return redirect('commission')


            # Lock godown row to prevent concurrent qty race conditions
            godown = Godowns.objects.select_for_update().get(pk=godown.pk)
            godown.qty -= qty_val
            godown.save()
            commission = get_object_for_user(Commissions, request.user, id=id)
            commission.godown_balance = godown.qty
            commission.expense = expense
            commission.godown = godown
            commission.date = dates[count]
            commission.qty = qty_val
            commission.amount = amount_val
            commission.total_amount = total_amount_val    
            commission.hold = False
            commission.client=getClient(request.user)
            commission.save()  
            count += 1
        return redirect('commission')


    


@method_decorator(never_cache, name='dispatch')
class CommissionHold(View):
    def post(self,request):
        with transaction.atomic():
            data = json.loads(request.body)
            commission_no = data.get('commission_no')
            expense = data.get('expense')
            godown = data.get('godown')
            date = data.get('date')
            try:
                qty = Decimal(str(data.get('qty', 0)))
                amount = Decimal(str(data.get('amount', 0)))
                total_amount = (qty * amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except Exception:
                return JsonResponse({'status': 'error', 'message': 'Invalid numeric data for qty or amount.'}, status=400)
            description = data.get('description')
    
            expense = get_object_for_user(Expenses, request.user, id=expense) if expense else None
            godown = get_object_for_user(Godowns, request.user, id=godown) if godown else None
            if data.get('commission_id'):
                commission = get_object_for_user(Commissions, request.user, id=data.get('commission_id'))
                # Lock godown row to prevent concurrent qty race conditions
                godown = Godowns.objects.select_for_update().get(pk=godown.pk)
                if not commission.hold:
                    godown.qty += commission.qty
                    godown.qty -= qty
                    godown.save()
                    commission.godown_balance -= commission.qty
                    commission.godown_balance += qty
                
                commission.commission_no = commission_no
                commission.expense = expense
                commission.godown = godown
                commission.date = date
                commission.qty = qty
                commission.amount = amount
                commission.total_amount = total_amount
                commission.description = description 
                commission.client=getClient(request.user)
                if not commission.hold:
                    commission.hold = False 
                commission.save()
                return JsonResponse({'status':'success','commission_id':commission.id,'hold':commission.hold})
            commission = Commissions.objects.create(
                commission_no=commission_no,
                expense=expense,
                godown=godown,
                date=date,
                qty=qty,
                amount=amount,
                total_amount=total_amount,
                description=description,
                hold=True,
                client=getClient(request.user)
            )
            return JsonResponse({'status':'success','commission_id':commission.id,'hold':commission.hold}) 
    
    
        


def getLastCommissionNo(client):
    last_commission_no = Commissions.objects.filter(is_active=True,client=client).order_by('-commission_no').first() 
    
    if last_commission_no and last_commission_no.commission_no.isdigit():
        new_commission_no = int(last_commission_no.commission_no) + 1
    else:
        new_commission_no = 1
    return new_commission_no


@login_required
@never_cache
def commission_no(request):
    new_commission_no = getLastCommissionNo(client=getClient(request.user))
    return JsonResponse({'commission_no': new_commission_no})


@login_required
@never_cache
def commissions_by_date(request):
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    commissions = []
    if from_date and to_date:
        commissions = Commissions.objects.filter(
            date__range=[parse_date(from_date), parse_date(to_date)],
            hold=False,
            is_active=True,
            client=getClient(request.user)
        ).select_related('expense', 'godown')
    commissionData = []
    total_qty = Decimal('0.0000')
    total_amount = Decimal('0.0000')
    rate_sum = Decimal('0.0000')
    count = 0
    for commission in commissions:
        commissionData.append({ 
            'id':commission.id,
            'commission_no':commission.commission_no,
            'expense':commission.expense.category if commission.expense else '',
            'expense_id':commission.expense.id if commission.expense else '',
            'godown':commission.godown.name if commission.godown else '',
            'godown_id':commission.godown.id if commission.godown else '',
            'date':str(commission.date),
            'qty':commission.qty,
            'amount':commission.amount,
            'total_amount':commission.total_amount,
            'description':commission.description if commission.description else '', 
        })
        total_qty += commission.qty
        total_amount += commission.total_amount
        rate_sum += commission.amount
        count += 1
    rate_avg = rate_sum / Decimal(str(count)) if count > 0 else Decimal('0.0000')
    return JsonResponse({'commissions': commissionData, 'total_qty': total_qty, 'total_amount': total_amount, 'rate_avg': rate_avg})


@never_cache
@require_POST
@transaction.atomic
def delete_commission(request):
    try:
        data = json.loads(request.body)
        pk = data.get('id')
    except json.JSONDecodeError:
        pk = request.POST.get('id')
        
    if not pk:
        return JsonResponse({'status': 'error', 'message': 'No ID provided'}, status=400)

    # Authorization: Ensure commission belongs to user's client
    commission = get_object_for_user(Commissions, request.user, id=pk)
    commission.is_active = False
    if not commission.hold:
        # Lock godown row to prevent concurrent qty race conditions
        godown_locked = Godowns.objects.select_for_update().get(pk=commission.godown.pk)
        godown_locked.qty += commission.qty
        godown_locked.save()
    commission.save()
    return JsonResponse({'status':'success','message':'commission deleted successfully'})