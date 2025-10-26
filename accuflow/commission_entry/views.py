import datetime
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Godowns,Commission,Expenses
from django.views import View
from django.views.generic.edit import DeleteView

class CommissionEntryView(View):
    def get(self,request):
        today = datetime.date.today()
        commissions = Commission.objects.filter(date=today)
        commissionData = []
        for commission in commissions:
            commissionData.append({
                'id':commission.id,
                'commission_no':commission.commission_no,
                'expense':commission.expense.category if commission.expense.category else '',
                'supplier_id':commission.expense.id if commission.expense else '',
                'godown':commission.godown.name if commission.godown else '',
                'godown_id':commission.godown.id if commission.godown else '',
                'date':str(commission.date),
                'qty':commission.qty,
                'amount':commission.amount,
                'total_amount':commission.total_amount,
                'description':commission.description if commission.description else '', 
            })
        expenses = Expenses.objects.filter(is_active=True)
        godowns = Godowns.objects.filter(is_active=True)
        context = {
            'cammissions':commissionData,
            'expenses':expenses,
            'godowns':godowns,
        }
        return render(request,'commission_entry/commission_entry.html',context)
    
    

class CommissionAddView(View):
    def post(self,request):
        today = datetime.date.today()
        dates = request.POST.getlist('dates')
        commission_nos = request.POST.getlist('commission_nos')
        total_amounts = request.POST.getlist('total_amounts')
        qtys = request.POST.getlist('qtys')
        amounts = request.POST.getlist('amounts')
        expenses_ids = request.POST.getlist('expenses')
        godown_ids = request.POST.getlist('godowns')
        count = 0
        for d in dates:
            
            expense = get_object_or_404(expense, id=expenses_ids[count]) if expenses_ids[count] else None
            godown = get_object_or_404(Godowns, id=godown_ids[count]) if godown_ids[count] else None
            Commission.objects.create(
                commission_no=commission_nos[count],
                expense=expense,
                godown=godown,
                date=dates[count],
                qty=qtys[count],
                amount=amounts[count],
                total_amount=total_amounts[count], 
            )
            count += 1
        return redirect('commission')
        
