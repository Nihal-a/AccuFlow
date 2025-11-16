from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Clients

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username,password=password)
        if user:
            login(request,user) 
            if user.is_admin:
                return redirect('clients')
            elif user.is_client:
                return redirect('customers')
            else:
                pass
        return redirect('login')
    return render(request, 'login.html') 


def user_logout(request):
    logout(request)    
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')
 

def getClient(user):
    if Clients.objects.filter(user=user,is_active=True).exists():
        return Clients.objects.get(user=user,is_active=True)
    else:
        return None
    
    
# def ledger_creator(where, to, purchase_amount, sale_amount):

#     where.debit += purchase_amount

#     if where.debit > 0 and where.credit > 0:
#         cancel = min(where.debit, where.credit)
#         where.debit -= cancel
#         where.credit -= cancel

#     where.balance = where.debit - where.credit
#     where.save()

#     to.credit += sale_amount

#     if to.debit > 0 and to.credit > 0:
#         cancel = min(to.debit, to.credit)
#         to.debit -= cancel
#         to.credit -= cancel

#     to.balance = to.debit - to.credit
#     to.save()



def update_party(party):
    if party.debit > 0 and party.credit > 0:
        cancel = min(party.debit, party.credit)
        party.debit -= cancel
        party.credit -= cancel

    party.balance = party.debit - party.credit
    party.save()


def update_ledger(where, to, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):
    # print(where.balance,to.balance)
    # print(new_purchase,old_purchase)
    # print(new_sale,old_sale) 
    if where:
        if old_purchase:
            where.debit = where.debit - float(old_purchase)
            if where.debit < 0:
                where.credit += abs(where.debit)
                where.debit = 0

        if new_purchase:
            print("before the + seller:",where.debit)
            where.debit += float(new_purchase)
        where.save()
        print("after the + seller:",where.debit)
        update_party(where)

    if to:
        if old_sale:
            to.credit = to.credit - float(old_sale)
            if to.credit < 0:
                to.debit += abs(to.credit)
                to.credit = 0

        if new_sale:
            to.credit += new_sale 
        to.save()
        print(to.debit,to.credit)
        update_party(to)


# def update_ledger(party, old_amount=0, new_amount=0):
#     if party is None:
#         return
    
#     if old_amount:
#         party.debit -= float(old_amount)

#     if new_amount:
#         party.debit += float(new_amount)

#     if party.debit < 0:
#         party.credit += abs(party.debit)
#         party.debit = 0

#     party.save()
#     update_party(party) 
    
    
# def update_godown_ledger(godown, old_amount=0, new_amount=0):
#     if godown is None:
#         return
    
#     if old_amount:
#         godown.credit -= float(old_amount)

#     if new_amount:
#         godown.credit += float(new_amount)

#     if godown.credit < 0:
#         godown.debit += abs(godown.credit)
#         godown.credit = 0

#     # cancel both if present
#     if godown.credit > 0 and godown.debit > 0:
#         cancel = min(godown.credit, godown.debit)
#         godown.credit -= cancel
#         godown.debit -= cancel

#     godown.balance = godown.debit - godown.credit
#     godown.save()

 