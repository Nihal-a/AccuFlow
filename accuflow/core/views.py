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
    if where and where != None:
        if old_purchase:
            where.credit = where.credit - float(old_purchase)
            if where.credit < 0:
                where.debit += abs(where.credit)
                where.credit = 0

        if new_purchase:
            print("before the + seller:",where.credit)
            where.credit += float(new_purchase)
        where.save()
        print("after the + seller:",where.credit)
        update_party(where)

    if to and where != None:
        if old_sale:
            to.debit = to.debit - float(old_sale)
            if to.debit < 0:
                to.credit += abs(to.debit)
                to.debit = 0

        if new_sale:
            to.debit += float(new_sale) 
        to.save()
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

 