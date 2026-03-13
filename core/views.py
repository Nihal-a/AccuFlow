from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Clients, Collection, Collectors, Customers, Expenses, Suppliers, TransactionType
from .services import FinancialService
from decimal import Decimal
from django.views import View
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)
 

TWOPLACES = Decimal('0.01')
 


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
 
            client_obj = None
            if user.is_client:
                 try:
                     client_obj = Clients.objects.get(user=user, is_active=True)
                 except Clients.DoesNotExist:
                     messages.error(request, "Your client record is inactive or not found.")
                     return redirect('login')
            elif user.is_collector:
                 try:
                     collector = Collectors.objects.get(user=user, is_active=True)
                     client_obj = collector.client
                 except Collectors.DoesNotExist:
                     messages.error(request, "Your collector record is inactive or not found.")
                     return redirect('login')
            
            if client_obj:
                 if client_obj.is_blocked:
                      messages.error(request, "Access denied. Your client account has been blocked. Please contact supporter.")
                      return redirect('login')
                 from django.utils import timezone
                 

                 if not client_obj.is_subscription_active:
                     messages.error(request, "Access denied. Your client's subscription has expired. Please contact your administrator.")
                     return redirect('login')
                 

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
                return redirect('dashboard')
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
 

@method_decorator(login_required, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class ClientDashboardView(View):
    def get(self, request):
        if not request.user.is_client:
            return redirect('login')
            
        client = getClient(request.user)
        if not client:
            return redirect('login')

        from django.db.models import Sum, Count
        from django.utils import timezone
        from .models import Purchases, Sales, NSDs, Cashs, Collection, Customers, Collectors, Suppliers, Expenses
        import calendar
        from datetime import date

        today = timezone.now().date()

        # --- Parse month/year from query param ---
        month_param = request.GET.get('month', '')
        is_year_view = month_param.startswith('year-')

        if is_year_view:
            try:
                sel_year = int(month_param.replace('year-', ''))
                if sel_year < 2000 or sel_year > 2100:
                    raise ValueError
            except ValueError:
                sel_year = today.year
            sel_month = today.month
            # For KPI cards, show full year
            month_start = date(sel_year, 1, 1)
            month_end = date(sel_year, 12, 31)
            selected_month = f"year-{sel_year}"
            month_display = f"Year {sel_year}"
        else:
            try:
                parts = month_param.split('-')
                sel_year = int(parts[0])
                sel_month = int(parts[1])
                if sel_month < 1 or sel_month > 12 or sel_year < 2000 or sel_year > 2100:
                    raise ValueError
            except (ValueError, IndexError):
                sel_year = today.year
                sel_month = today.month
            month_start = date(sel_year, sel_month, 1)
            month_end = date(sel_year, sel_month, calendar.monthrange(sel_year, sel_month)[1])
            selected_month = f"{sel_year}-{sel_month:02d}"
            month_display = month_start.strftime('%B %Y')

        # Build picker options: last 12 months + last 3 years
        available_months = []
        d = today.replace(day=1)
        for _ in range(12):
            available_months.append({
                'value': f"{d.year}-{d.month:02d}",
                'label': d.strftime('%B %Y'),
            })
            if d.month == 1:
                d = d.replace(year=d.year - 1, month=12)
            else:
                d = d.replace(month=d.month - 1)
        # Add year options
        for yr in range(today.year, today.year - 3, -1):
            available_months.append({
                'value': f"year-{yr}",
                'label': f"── Year {yr} ──",
            })

        # Date filter kwargs for transactions
        date_filter = {'date__gte': month_start, 'date__lte': month_end}
        base_kwargs = {'client': client, 'is_active': True, 'hold': False}

        # Purchase Metrics
        purchase_stats = Purchases.objects.filter(**base_kwargs, **date_filter).aggregate(
            count=Count('id'), total=Sum('total_amount'))
        
        # Sale Metrics
        sale_stats = Sales.objects.filter(**base_kwargs, **date_filter).aggregate(
            count=Count('id'), total=Sum('total_amount'))
            
        # NSD Metrics
        nsd_stats = NSDs.objects.filter(**base_kwargs, **date_filter).aggregate(
            count=Count('id'), total=Sum('sell_amount'))
            
        # Cash/Bank Metrics (Net Cash Flow)
        c_rcv = Cashs.objects.filter(transaction=TransactionType.RECEIVED, **base_kwargs, **date_filter).aggregate(c=Count('id'), t=Sum('amount'))
        c_paid = Cashs.objects.filter(transaction=TransactionType.PAID, **base_kwargs, **date_filter).aggregate(c=Count('id'), t=Sum('amount'))
        cash_stats = {
            'count': (c_rcv['c'] or 0) + (c_paid['c'] or 0),
            'total': (c_rcv['t'] or Decimal('0')) - (c_paid['t'] or Decimal('0'))
        }

        # Approved Collections
        approved_col_stats = Collection.objects.filter(client=client, status='Approved', is_active=True, **date_filter).aggregate(
            count=Count('id'), total=Sum('total_amount'))
            
        # Pending Collections
        pending_col_stats = Collection.objects.filter(client=client, status='Pending', is_active=True, **date_filter).aggregate(
            count=Count('id'), total=Sum('total_amount'))

        # Top 5 Outstanding Customers (cumulative, not filtered)
        outstanding_customers = Customers.objects.filter(client=client, is_active=True, balance__gt=0).order_by('-balance')[:5]

        # Recent collections for selected period
        recent_collections = Collection.objects.filter(
            client=client, is_active=True, **date_filter
        ).select_related('collector').order_by('-date', '-id')[:5]
        
        # Subscription status
        days_remaining = 0
        if client.subscription_end:
            days_remaining = (client.subscription_end - timezone.now().date()).days
            if days_remaining < 0: days_remaining = 0

        # --- Chart data ---
        import json
        from datetime import timedelta

        chart_labels = []
        chart_purchase = []
        chart_sale = []
        chart_nsd = []
        chart_cash = []

        if is_year_view:
            # Year view: monthly totals for each month of the year
            for mo in range(1, 13):
                mo_start = date(sel_year, mo, 1)
                mo_end = date(sel_year, mo, calendar.monthrange(sel_year, mo)[1])
                mo_filter = {'date__gte': mo_start, 'date__lte': mo_end}
                chart_labels.append(mo_start.strftime('%b'))

                p = Purchases.objects.filter(client=client, is_active=True, hold=False, **mo_filter).aggregate(t=Sum('total_amount'))
                chart_purchase.append(str(p['t'] or Decimal('0.0000')))
                s = Sales.objects.filter(client=client, is_active=True, hold=False, **mo_filter).aggregate(t=Sum('total_amount'))
                chart_sale.append(str(s['t'] or Decimal('0.0000')))
                n = NSDs.objects.filter(client=client, is_active=True, hold=False, **mo_filter).aggregate(t=Sum('sell_amount'))
                chart_nsd.append(str(n['t'] or Decimal('0.0000')))
                
                c_in = Cashs.objects.filter(client=client, is_active=True, hold=False, transaction=TransactionType.RECEIVED, **mo_filter).aggregate(t=Sum('amount'))
                c_out = Cashs.objects.filter(client=client, is_active=True, hold=False, transaction=TransactionType.PAID, **mo_filter).aggregate(t=Sum('amount'))
                net_cash = float((c_in['t'] or Decimal('0')) - (c_out['t'] or Decimal('0')))
                chart_cash.append(net_cash)
        else:
            # Month view: daily totals for each day
            def daily_totals(model, value_field, extra_filter=None):
                q = model.objects.filter(client=client, is_active=True, hold=False, **date_filter)
                if extra_filter:
                    q = q.filter(**extra_filter)
                rows = (
                    q.values('date')
                    .annotate(total=Sum(value_field))
                    .order_by('date')
                )
                result = {}
                for row in rows:
                    rd = row['date']
                    if hasattr(rd, 'date'):
                        rd = rd.date()
                    result[rd] = str(row['total'] or Decimal('0.0000'))
                return result

            p_daily = daily_totals(Purchases, 'total_amount')
            s_daily = daily_totals(Sales, 'total_amount')
            n_daily = daily_totals(NSDs, 'sell_amount')
            
            c_in_daily = daily_totals(Cashs, 'amount', {'transaction': TransactionType.RECEIVED})
            c_out_daily = daily_totals(Cashs, 'amount', {'transaction': TransactionType.PAID})

            current_day = month_start
            while current_day <= month_end:
                chart_labels.append(current_day.strftime('%d'))
                chart_purchase.append(p_daily.get(current_day, "0.0000"))
                chart_sale.append(s_daily.get(current_day, "0.0000"))
                chart_nsd.append(n_daily.get(current_day, "0.0000"))
                
                in_val = Decimal(c_in_daily.get(current_day, "0.0000"))
                out_val = Decimal(c_out_daily.get(current_day, "0.0000"))
                net_day_cash = str(in_val - out_val)
                chart_cash.append(net_day_cash)
                current_day += timedelta(days=1)

        chart_data = {
            'labels': chart_labels,
            'purchase': chart_purchase,
            'sale': chart_sale,
            'nsd': chart_nsd,
            'cash': chart_cash,
        }

        context = {
            'purchase_stats': purchase_stats,
            'sale_stats': sale_stats,
            'nsd_stats': nsd_stats,
            'cash_stats': cash_stats,
            'approved_col_stats': approved_col_stats,
            'pending_col_stats': pending_col_stats,
            'outstanding_customers': outstanding_customers,
            'recent_collections': recent_collections,
            'client': client,
            'days_remaining': days_remaining,
            'total_customers': Customers.objects.filter(client=client, is_active=True).count(),
            'selected_month': selected_month,
            'month_display': month_display,
            'available_months': available_months,
            'chart_data_json': chart_data,
        }
        return render(request, 'dashboard/client_dashboard.html', context)


def getClient(user, request=None):
    # PERF-10: Cache on request to avoid repeated DB lookups per request
    cache_attr = '_cached_client'
    if request and hasattr(request, cache_attr):
        return getattr(request, cache_attr)
    
    from .models import Clients, Collectors
    client = None
    if user.is_client:
        try:
            client = Clients.objects.get(user=user, is_active=True)
        except Clients.DoesNotExist:
            pass
    elif user.is_collector:
        try:
            collector = Collectors.objects.select_related('client').get(user=user, is_active=True)
            client = collector.client
        except Collectors.DoesNotExist:
            pass
    
    if request:
        setattr(request, cache_attr, client)
    return client
       

def update_party(party):
    if party.debit > 0 and party.credit > 0:
        cancel = min(party.debit, party.credit)
        party.debit -= cancel
        party.credit -= cancel
    
    party.balance = (party.debit - party.credit).quantize(TWOPLACES)


def calculate_supplier_balance(supplier, client, date_limit=None):
    from core.models import Purchases, Sales, NSDs, Cashs
    from django.db.models import Sum, Q

    base_filter = Q(is_active=True, hold=False, client=client, supplier=supplier)
    nsd_base = Q(is_active=True, hold=False, client=client)
    
    if date_limit:
        base_filter &= Q(date__lte=date_limit)
        nsd_base &= Q(date__lte=date_limit)
    
    purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
    sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
    sender_sum = NSDs.objects.filter(nsd_base, sender_supplier=supplier).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
    receiver_sum = NSDs.objects.filter(nsd_base, receiver_supplier=supplier).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
    
    cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    
    transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
    static_ob = supplier.open_debit - supplier.open_credit
    
    return (static_ob + transaction_balance).quantize(TWOPLACES)

def calculate_customer_balance(customer, client, date_limit=None):
    from core.models import Purchases, Sales, NSDs, Cashs
    from django.db.models import Sum, Q

    base_filter = Q(is_active=True, hold=False, client=client, customer=customer)
    nsd_base = Q(is_active=True, hold=False, client=client)
    
    if date_limit:
        base_filter &= Q(date__lte=date_limit)
        nsd_base &= Q(date__lte=date_limit)
    
    purchases_sum = Purchases.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
    sales_sum = Sales.objects.filter(base_filter).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.0000')
    sender_sum = NSDs.objects.filter(nsd_base, sender_customer=customer).aggregate(s=Sum('purchase_amount'))['s'] or Decimal('0.0000')
    receiver_sum = NSDs.objects.filter(nsd_base, receiver_customer=customer).aggregate(s=Sum('sell_amount'))['s'] or Decimal('0.0000')
    
    cash_received = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    cash_paid = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    
    transaction_balance = (sales_sum + receiver_sum + cash_paid) - (purchases_sum + sender_sum + cash_received)
    static_ob = customer.open_debit - customer.open_credit
    
    return (static_ob + transaction_balance).quantize(TWOPLACES)

def calculate_cashbank_balance(cashbank, client, date_limit=None):
    from core.models import Cashs
    from django.db.models import Sum, Q
    from decimal import Decimal

    base_filter = Q(is_active=True, hold=False, client=client, cash_bank=cashbank)
    if date_limit:
        base_filter &= Q(date__lte=date_limit)
        
    received_sum = Cashs.objects.filter(base_filter, transaction="Received").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    paid_sum = Cashs.objects.filter(base_filter, transaction="Paid").aggregate(s=Sum('amount'))['s'] or Decimal('0.0000')
    
    return (received_sum - paid_sum).quantize(TWOPLACES)


@transaction.atomic
def update_ledger(where, to=None, old_purchase=0, new_purchase=0, old_sale=0, new_sale=0):
    FinancialService.update_ledger(where, to, old_purchase, new_purchase, old_sale, new_sale)


@login_required
@require_POST
def mark_notifications_read(request):
    client = getClient(request.user)
    if client:
        if request.user.is_collector:
            collector = getattr(request.user, 'collectors_set').first()
            if collector:
                Collection.objects.filter(collector=collector, status__in=['New', 'Approved', 'Rejected'], is_viewed=False).update(is_viewed=True)
        else:
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

@login_required
@require_POST
def verify_admin_action_password(request):
    import json
    from django.conf import settings
    
    try:
        data = json.loads(request.body)
        password = data.get('password')
        
        from django.utils.crypto import constant_time_compare
        
        if password and constant_time_compare(str(password), str(settings.ADMIN_ACTION_PASSWORD)):
            request.session['admin_action_authorized'] = True
            request.session.modified = True
            request.session.save()
            return JsonResponse({'status': 'success'})
        else:
            # Simple comment test
            return JsonResponse({'status': 'error', 'message': 'Invalid secret key'})
    except Exception as e:
        logger.exception("verify_admin_action_password failed")
        return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred'})

@login_required
@require_POST
def lock_admin_actions(request):
    if 'admin_action_authorized' in request.session:
        del request.session['admin_action_authorized']
        request.session.modified = True
    return JsonResponse({'status': 'success'})

def handler404(request, exception=None, *args, **kwargs):
    return render(request, '404.html', status=404)

def handler403(request, exception=None, *args, **kwargs):
    # Security: Show 404 instead of 403 to avoid revealing resource existence
    return render(request, '404.html', status=404)
