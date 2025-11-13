import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Commissions,Expenses,Godowns
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient

class CommissionEntryView(View):
    def get(self,request):
        commissions = Commissions.objects.filter(hold=True,is_active=True,client=getClient(request.user))
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
        expenses = Expenses.objects.filter(is_active=True,client=getClient(request.user))
        godowns = Godowns.objects.filter(is_active=True,client=getClient(request.user))
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
            'last_commission_no':getLastCommissionNo(client=getClient(request.user)),
        }
        return render(request,'commission_entry/commission_entry.html',context)
    
    

class CommissionAddView(View):
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
            expense = get_object_or_404(Expenses, id=expense_ids[count]) if expense_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            commission = Commissions.objects.get(id=id)
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


    


class CommissionHold(View):
    def post(self,request):
        data = json.loads(request.body)
        commission_no = data.get('commission_no')
        expense = data.get('expense')
        godown = data.get('godown')
        date = data.get('date')
        qty = data.get('qty')
        amount = data.get('amount')
        total_amount = data.get('total_amount')
        description = data.get('description')

        expense = get_object_or_404(Expenses, id=expense) if expense else None
        godown = get_object_or_404(Godowns, id=godown) if godown else None
        if data.get('commission_id'):
            commission = get_object_or_404(Commissions, id=data.get('commission_id'))
            
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


def commission_no(request):
    new_commission_no = getLastCommissionNo(client=getClient(request.user))
    return JsonResponse({'commission_no': new_commission_no})


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
        )
    commissionData = []
    total_qty = 0
    total_amount = 0
    rate_sum = 0
    count = 0
    for commission in commissions:
        commissionData.append({ 
            'id':commission.id,
            'commission_no':commission.commission_no,
            'expense':commission.expense.category if commission.expense else '',
            'expense':commission.expense.id if commission.expense else '',
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
    rate_avg = rate_sum / count if count > 0 else 0
    return JsonResponse({'commissions': commissionData, 'total_qty': total_qty, 'total_amount': total_amount, 'rate_avg': rate_avg})


def delete_commission(request):
    pk = request.GET.get('id') 
    commission = get_object_or_404(Commissions, id=pk)
    commission.is_active = False
    commission.save()
    return JsonResponse({'status':'success','message':'commission deleted successfully'})