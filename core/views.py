from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Clients, Collection, Collectors
from decimal import Decimal
 


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
 
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
                 

                 if not client_obj.is_subscription_active:
                     login(request, user)
                     user.last_session_key = request.session.session_key
                     user.save(update_fields=['last_session_key'])
                     return redirect('subscription_expired')
                 

                 if client_obj.subscription_end:
                     days_left = (client_obj.subscription_end - timezone.now().date()).days
                     if 0 <= days_left <= 7:
                         messages.warning(request, f"Your subscription expires in {days_left} days. Please renew soon.")

            login(request,user) 
            
            # Update last session key for single session enforcement
            user.last_session_key = request.session.session_key
            user.save(update_fields=['last_session_key'])

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

        if Decimal(old_purchase) > 0: 
            where.credit -= Decimal(old_purchase)
            if where.credit < 0:
                where.debit += abs(where.credit)
                where.credit = 0

        if Decimal(new_purchase) > 0:
            where.credit += Decimal(new_purchase)

        update_party(where)
        where.save()

    if to:
        to.refresh_from_db()

        if Decimal(old_sale) > 0:
            to.debit -= Decimal(old_sale)
            if to.debit < 0:
                to.credit += abs(to.debit)
                to.debit = 0

        if Decimal(new_sale) > 0:
            to.debit += Decimal(new_sale)

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

from .models import SubscriptionPlan
@login_required
def get_plan_details(request, plan_id):
    if not request.user.is_staff: # Ensure only staff/admin can access
         return JsonResponse({'error': 'Unauthorized'}, status=403)
         
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
        return JsonResponse({'price': plan.price})
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'error': 'Plan not found'}, status=404)