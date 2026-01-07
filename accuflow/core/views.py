from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Clients, Collection

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
            elif user.is_collector:
                return redirect('my_collections')
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
       

def update_party(party):
    if party.debit > 0 and party.credit > 0:
        cancel = min(party.debit, party.credit)
        party.debit -= cancel
        party.credit -= cancel
    
    party.balance = party.debit - party.credit


def update_ledger(where, to=None, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):

    if where:
        where.refresh_from_db()

        if float(old_purchase) > 0:
            where.credit -= float(old_purchase)
            if where.credit < 0:
                where.debit += abs(where.credit)
                where.credit = 0

        if float(new_purchase) > 0:
            where.credit += float(new_purchase)

        update_party(where)
        where.save()

    if to:
        to.refresh_from_db()

        if float(old_sale) > 0:
            to.debit -= float(old_sale)
            if to.debit < 0:
                to.credit += abs(to.debit)
                to.debit = 0

        if float(new_sale) > 0:
            to.debit += float(new_sale)

        update_party(to)
        to.save()

@login_required
@require_POST
def mark_notifications_read(request):
    client = getClient(request.user)
    if client:
        Collection.objects.filter(client=client, status='Pending', is_viewed=False).update(is_viewed=True)
    elif request.user.is_superuser:
        Collection.objects.filter(status='Pending', is_viewed=False).update(is_viewed=True)
        
    return JsonResponse({'status': 'success'})


