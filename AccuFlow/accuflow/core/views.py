from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Clients, Collection, Collectors

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username,password=password)
        if user:
            # Check Subscription Status for Client and Collector 
            client_obj = None
            if user.is_client:
                 try:
                     client_obj = Clients.objects.get(user=user)
                 except Clients.DoesNotExist:
                     pass
            elif user.is_collector:
                 try:
                     collector = Collectors.objects.get(user=user)
                     client_obj = collector.client
                 except Collectors.DoesNotExist:
                     pass
            
            if client_obj:
                 from django.utils import timezone
                 
                 # Check if expired
                 if not client_obj.is_subscription_active:
                     login(request, user) # Login to establish session
                     return redirect('subscription_expired')
                 
                 # Check if expiring within 7 days
                 if client_obj.subscription_end:
                     days_left = (client_obj.subscription_end - timezone.now().date()).days
                     if 0 <= days_left <= 7:
                         messages.warning(request, f"Your subscription expires in {days_left} days. Please renew soon.")

            login(request,user) 
            if user.is_admin:
                return redirect('clients')
            elif user.is_client:
                return redirect('customers')
            elif user.is_collector:
                return redirect('my_collections')
            else:
                pass
        else:
             messages.error(request, "Invalid username or password.")
        return redirect('login')
    return render(request, 'login.html')

def user_logout(request):
    logout(request)    
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')

def getClient(user):
    if user.is_client:
         return Clients.objects.get(user=user)
    elif user.is_collector:
         return Collectors.objects.get(user=user).client
    return None

def update_party(party):
    if party.debit > party.credit:
        party.debit -= party.credit
        party.credit = 0
    elif party.credit > party.debit:
        party.credit -= party.debit
        party.debit = 0
    else:
        party.debit = 0
        party.credit = 0
    return party



def update_ledger(where=None, to=None, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):
    if where:
        where.refresh_from_db()
        
        # Handle Purchase (Credit)
        if float(old_purchase) > 0:
            where.credit -= float(old_purchase)
            if where.credit < 0:
                where.debit += abs(where.credit)
                where.credit = 0
        
        if float(new_purchase) > 0:
            where.credit += float(new_purchase)

        # Handle Sale (Debit)
        if float(old_sale) > 0:
            where.debit -= float(old_sale)
            if where.debit < 0:
                where.credit += abs(where.debit)
                where.debit = 0
        
        if float(new_sale) > 0:
            where.debit += float(new_sale)
            
        update_party(where)
        where.save()

def update_customer_balance(to,old_sale,new_sale):
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

def subscription_expired(request):
    return render(request, 'subscription_expired.html')
