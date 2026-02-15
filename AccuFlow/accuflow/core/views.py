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
                     return redirect('subscription_expired')
                 

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



from django.db import transaction
from decimal import Decimal, InvalidOperation

@transaction.atomic
def update_ledger(where=None, to=None, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):
    # Ensure all numerical inputs are Decimals for consistent arithmetic
    def to_decimal(val):
        try:
            return Decimal(str(val or 0))
        except (ValueError, TypeError, InvalidOperation):
            return Decimal('0.0000')

    old_p = to_decimal(old_purchase)
    new_p = to_decimal(new_purchase)
    old_s = to_decimal(old_sale)
    new_s = to_decimal(new_sale)

    # Handle 'where' argument (Suppliers/Customers)
    if where:
        # Lock the row for update
        obj_class = where.__class__
        where = obj_class.objects.select_for_update().get(pk=where.pk)
        
        # Ensure model fields are also Decimals to avoid float + Decimal issues
        where.credit = to_decimal(where.credit)
        where.debit = to_decimal(where.debit)
        
        if old_p > 0:
            where.credit -= old_p
            if where.credit < 0:
                where.debit += abs(where.credit)
                where.credit = Decimal('0.0000')
        
        if new_p > 0:
            where.credit += new_p

        if old_s > 0:
            where.debit -= old_s
            if where.debit < 0:
                where.credit += abs(where.debit)
                where.debit = Decimal('0.0000')
        
        if new_s > 0:
            where.debit += new_s
            
        update_party(where)
        where.save()

    if to:
        obj_class = to.__class__
        to = obj_class.objects.select_for_update().get(pk=to.pk)

        # Ensure model fields are also Decimals
        to.credit = to_decimal(to.credit)
        to.debit = to_decimal(to.debit)

        if old_s > 0:
            to.debit -= old_s
            if to.debit < 0:
                to.credit += abs(to.debit)
                to.debit = Decimal('0.0000')

        if new_s > 0:
            to.debit += new_s
            
        if old_p > 0:
             to.credit -= old_p
             if to.credit < 0:
                 to.debit += abs(to.credit)
                 to.credit = Decimal('0.0000')
        
        if new_p > 0:
            to.credit += new_p

        update_party(to)
        to.save()

def update_customer_balance(to,old_sale,new_sale):
    if to:
        update_ledger(to=to, old_sale=old_sale, new_sale=new_sale)


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

