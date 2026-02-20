from django.shortcuts import render,redirect, get_object_or_404
from core.models import Expenses
from django.views import View
from django.views.generic.edit import DeleteView

from core.views import getClient
from core.authorization import get_object_for_user

class ExpenseView(View):
    def get(self,request):
        expenses = Expenses.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'expenses/expenses.html',{'expenses':expenses})


class AddExpenseView(View):
    def get(self,request):
        return render(request,'expenses/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        description = request.POST.get('description')
        Expenses.objects.create(
            category=name,
            description=description,
            client=getClient(request.user)
        )
        return redirect('expenses')

class DeleteExpenseView(View):
    def post(self, request, expense_id):
        expense = get_object_for_user(Expenses, request.user, id=expense_id)
        expense.is_active = False 
        expense.save()
        return redirect('expenses')
 

class UpdateExpenseView(View):
    def get(self, request, expense_id):
        expense = get_object_for_user(Expenses, request.user, id=expense_id)
        return render(request, 'expenses/update.html', {'expense': expense})

    def post(self, request, expense_id):
        expense = get_object_for_user(Expenses, request.user, id=expense_id)
        expense.category = request.POST.get('name')
        expense.description = request.POST.get('description')
        expense.save()
        return redirect('expenses')