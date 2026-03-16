import json
import logging
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Clients, UserAccount, SubscriptionPlan
from django.utils import timezone
from datetime import timedelta 
from django.views import View
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Sum
from core.decorators import admin_action_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminDashboardView(View):
    def get(self, request):
        from core.models import SubscriptionPayment, AdminExpense
        import datetime
        
        clients = Clients.objects.filter(is_active=True)
        total_clients = clients.count()
        
        active_subs = 0
        expired_subs = 0
        renewals_due = []
        
        today = timezone.now().date()
        reminder_threshold = today + datetime.timedelta(days=7)
        
        for client in clients:
            if client.is_subscription_active:
                active_subs += 1
                if client.subscription_end and today <= client.subscription_end <= reminder_threshold:
                    renewals_due.append({
                        'client': client,
                        'days_left': (client.subscription_end - today).days
                    })
            else:
                expired_subs += 1
                
        renewals_due = sorted(renewals_due, key=lambda x: x['days_left'])
        
        total_revenue = SubscriptionPayment.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        total_expenses = AdminExpense.objects.filter(is_active=True).aggregate(Sum('amount'))['amount__sum'] or 0
        profit = total_revenue - total_expenses

        recent_payments = SubscriptionPayment.objects.select_related('client', 'plan').order_by('-date')[:5]
        recent_expenses = AdminExpense.objects.filter(is_active=True).order_by('-date', '-id')[:5]
        
        context = {
            'total_clients': total_clients,
            'active_subs': active_subs,
            'expired_subs': expired_subs,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'profit': profit,
            'recent_payments': recent_payments,
            'recent_expenses': recent_expenses,
            'renewals_due': renewals_due
        }
        
        return render(request, 'admin/dashboard/dashboard.html', context)

@method_decorator([login_required, staff_member_required], name='dispatch')
class ClientsView(View):
    def get(self, request):
        from core.models import SubscriptionPayment
        from django.db.models import Prefetch
        from django.utils import timezone
        import datetime
        
        status_filter = request.GET.get('status', 'all')
        
        payment_prefetch = Prefetch(
            'subscriptionpayment_set',
            queryset=SubscriptionPayment.objects.select_related('plan').order_by('-date'),
            to_attr='all_payments'
        )
        
        clients_query = Clients.objects.filter(is_active=True).select_related('user', 'subscription_plan').prefetch_related(payment_prefetch).order_by('-id')
        
        clients = []
        upcoming_renewals = []
        today = timezone.now().date()
        reminder_threshold = today + datetime.timedelta(days=7)
        
        for client in clients_query:
            client.total_paid = sum(p.amount for p in client.all_payments)
            is_active_sub = client.is_subscription_active
            
            if status_filter == 'active' and not is_active_sub:
                continue
            if status_filter == 'expired' and is_active_sub:
                continue
                
            # Check for upcoming renewal (expiring in <= 7 days and not already expired)
            if is_active_sub and client.subscription_end and today <= client.subscription_end <= reminder_threshold:
                days_left = (client.subscription_end - today).days
                upcoming_renewals.append({
                    'client': client,
                    'days_left': days_left
                })
                
            clients.append(client)
            
        return render(request, 'admin/clients/clients.html', {
            'clients': clients,
            'current_status': status_filter,
            'upcoming_renewals': sorted(upcoming_renewals, key=lambda x: x['days_left'])
        })
    


@method_decorator([login_required, staff_member_required], name='dispatch')
class ClientAddView(View):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'admin/clients/create.html', {
            'plans': plans,
            'next_id': last_client_id()
        })

    def post(self, request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        wa = request.POST.get('wa')
        country_code = request.POST.get('country_code', '+971')
        has_whatsapp_access = request.POST.get('has_whatsapp_access') == 'on'
        username = request.POST.get('username')
        client_id_val = request.POST.get('clientId')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('create-client')

        if UserAccount.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('create-client')

        if client_id_val and Clients.objects.filter(clientId=client_id_val, is_active=True).exists():
            messages.error(request, "Client ID already taken.")
            return redirect('create-client')

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('create-client')

        user = UserAccount.objects.create_client(
            username=username,
            password=password,
        )
        # Robustly handle clientId
        client_id_posted = client_id_val.strip() if client_id_val else ""
        if not client_id_posted or client_id_posted.lower() in ['none', 'null']:
            final_client_id = last_client_id()
        else:
            final_client_id = client_id_posted

        client = Clients.objects.create(
            name=name,
            phone=phone,
            email=email,
            user=user,
            wa=wa,
            country_code=country_code,
            has_whatsapp_access=has_whatsapp_access,
            is_active=True,
            clientId=final_client_id
        )
        

        plan_id = request.POST.get('subscription_plan')
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                client.subscription_plan = plan
                client.subscription_start = timezone.now().date()
                

                custom_duration = request.POST.get('custom_duration')
                if custom_duration and custom_duration.isdigit():
                     duration = int(custom_duration)
                else:
                     duration = plan.duration_days
                
                client.subscription_end = timezone.now().date() + timedelta(days=duration)
                client.is_trial_active = plan.is_trial
                client.save()
            except SubscriptionPlan.DoesNotExist:
                pass

        messages.success(request, f"Client '{name}' created successfully!")
        return redirect('clients')
    
    
@method_decorator([login_required, staff_member_required], name='dispatch')
class ClientUpdateView(View):
    def get(self,request,id):

        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can manage clients")
        
        client = get_object_or_404(Clients, id=id, is_active=True)
        user = client.user
        subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
        context = {
            'client': client,
            'user': user,
            'subscription_plans': subscription_plans,
        }
        return render(request, 'admin/clients/update.html', context)    
    def post(self,request,id):

        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can manage clients")
        
        client = get_object_or_404(Clients, id=id, is_active=True)
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        wa = request.POST.get('wa')
        country_code = request.POST.get('country_code')
        client_id_val = request.POST.get('clientId')
        has_whatsapp_access = request.POST.get('has_whatsapp_access') == 'on'
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        user = client.user
        
        if password and password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('update-client', id=client.id)

        if UserAccount.objects.exclude(id=user.id).filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('update-client', id=client.id)

        if client_id_val and Clients.objects.exclude(id=client.id).filter(clientId=client_id_val, is_active=True).exists():
            messages.error(request, "Client ID already taken by another active client.")
            return redirect('update-client', id=client.id)

        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
                return redirect('update-client', id=client.id)

        client.name = name
        client.email = email
        client.phone = phone
        client.country_code = country_code

        # Robustly handle clientId: check for empty, None, or literal null strings
        client_id_posted = client_id_val.strip() if client_id_val else ""
        if not client_id_posted or client_id_posted.lower() in ['none', 'null']:
            client.clientId = last_client_id()
        else:
            client.clientId = client_id_posted
        client.has_whatsapp_access = has_whatsapp_access


        plan_id = request.POST.get('subscription_plan')
        if plan_id:
            try:
                new_plan = SubscriptionPlan.objects.get(id=plan_id)
                

                custom_duration = request.POST.get('custom_duration')
                duration = None
                if custom_duration and custom_duration.isdigit():
                    duration = int(custom_duration)


                if (not client.subscription_plan or client.subscription_plan.id != new_plan.id) or duration:
                    client.subscription_plan = new_plan
                    client.subscription_start = timezone.now().date()
                    
                    if duration is None:
                        duration = new_plan.duration_days
                        
                    client.subscription_end = timezone.now().date() + timedelta(days=duration)
                    client.is_trial_active = new_plan.is_trial
            except SubscriptionPlan.DoesNotExist:
                pass
        
        client.save()

        user.username = username
        if password:
            user.password = make_password(password)
        user.save()

        messages.success(request, "Client updated successfully.")
        return redirect('clients')

        

@method_decorator([login_required, staff_member_required], name='dispatch')
class DeleteClientView(View):
    def post(self, request, client_id):

        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can delete clients")
        
        client = get_object_or_404(Clients, id=client_id)
        
        # Soft delete the client using the mixin's method
        client.soft_delete()
        
        # Also disable their user account so they can't log in
        if hasattr(client, 'user') and client.user:
            client.user.is_active = False
            client.user.save()
            
        messages.success(request, f"Client '{client.name}' moved to recycle bin.")
        return redirect('clients')

@login_required
@staff_member_required
@never_cache
@require_POST
def toggle_client_block(request, client_id):
    client = get_object_or_404(Clients, id=client_id)
    client.is_blocked = not client.is_blocked
    client.save()
    status = "blocked" if client.is_blocked else "unblocked"
    messages.success(request, f"Client '{client.name}' has been {status}.")
    return redirect('clients')



def last_client_id():
    client_ids = Clients.objects.filter(clientId__regex=r'^AF-\d+$').values_list('clientId', flat=True)
    
    max_num = 0
    for cid in client_ids:
        try:
            num = int(cid.split('-')[1])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            continue
            
    return f"AF-{max_num + 1}"




from django.core.cache import cache

@login_required
def check_username_availability(request):
    if request.method == 'POST':
        # MED-11: Simple Rate Limiting (max 10 requests per minute per IP)
        ip = request.META.get('REMOTE_ADDR')
        cache_key = f'username_check_rate_limit_{ip}'
        requests_count = cache.get(cache_key, 0)
        
        if requests_count >= 10:
            return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
            
        cache.set(cache_key, requests_count + 1, timeout=60)
        
        try:
            data = json.loads(request.body.decode('utf-8'))
            username = data.get('username', '').strip()
            exists = UserAccount.objects.filter(username=username).exists()
            return JsonResponse({'available': not exists})
        except Exception as e:
            logger.error(f"Error checking username availability: {e}", exc_info=True)
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@method_decorator([login_required, staff_member_required], name='dispatch')
class SubscriptionListView(View):
    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        return render(request, 'admin/subscriptions/list.html', {'plans': plans})

@method_decorator([login_required, staff_member_required], name='dispatch')
class SubscriptionCreateView(View):
    def get(self, request):
        return render(request, 'admin/subscriptions/form.html')

    def post(self, request):
        name = request.POST.get('name')
        price = request.POST.get('price')
        duration = request.POST.get('duration')
        is_trial = request.POST.get('is_trial') == 'on'
        description = request.POST.get('description')

        SubscriptionPlan.objects.create(
            name=name,
            price=price,
            duration_days=duration,
            is_trial=is_trial,
            description=description,
            is_active=True
        )
        messages.success(request, "Subscription Plan created.")
        return redirect('subscriptions')

@method_decorator([login_required, staff_member_required], name='dispatch')
class SubscriptionUpdateView(View):
    def get(self, request, id):

        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can manage subscription plans")
        
        plan = get_object_or_404(SubscriptionPlan, id=id)
        return render(request, 'admin/subscriptions/form.html', {'plan': plan})

    def post(self, request, id):

        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can manage subscription plans")
        
        plan = get_object_or_404(SubscriptionPlan, id=id)
        
        plan.name = request.POST.get('name')
        plan.price = request.POST.get('price')
        plan.duration_days = request.POST.get('duration')
        plan.is_trial = request.POST.get('is_trial') == 'on'
        plan.description = request.POST.get('description')
        plan.is_active = request.POST.get('is_active') == 'on'
        plan.save()

        messages.success(request, "Subscription Plan updated.")
        return redirect('subscriptions')

from core.models import SubscriptionPayment

@method_decorator([login_required, staff_member_required], name='dispatch')
class PaymentListView(View):
    def get(self, request):
        payments = SubscriptionPayment.objects.select_related('client', 'plan').order_by('-date')
        return render(request, 'admin/subscription_payments/list.html', {'payments': payments})

@method_decorator([login_required, staff_member_required], name='dispatch')
class PaymentCreateView(View):
    def get(self, request):
        clients = Clients.objects.filter(is_active=True)
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'admin/subscription_payments/create.html', {
            'clients': clients,
            'plans': plans
        })

    def post(self, request):
        client_id = request.POST.get('client_id')
        plan_id = request.POST.get('plan_id')
        amount = request.POST.get('amount')
        transaction_id = request.POST.get('transaction_id')
        payment_method = request.POST.get('payment_method')
        is_renewal = request.POST.get('is_renewal') == 'on'

        try:
            client = Clients.objects.get(id=client_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            SubscriptionPayment.objects.create(
                client=client,
                plan=plan,
                amount=amount,
                transaction_id=transaction_id,
                payment_method=payment_method,
                is_renewal=is_renewal
            )
            
            messages.success(request, f"Payment recorded for {client.name}")
            return redirect('payments')
            
        except (Clients.DoesNotExist, SubscriptionPlan.DoesNotExist):
            messages.error(request, "Invalid Client or Plan selected.")
            return redirect('payment-create')
@method_decorator([login_required, staff_member_required], name='dispatch')
class PaymentUpdateView(View):
    def get(self, request, id):
        payment = get_object_or_404(SubscriptionPayment, id=id)
        clients = Clients.objects.filter(is_active=True)
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'admin/subscription_payments/create.html', {
            'payment': payment,
            'clients': clients,
            'plans': plans
        })

    def post(self, request, id):
        payment = get_object_or_404(SubscriptionPayment, id=id)
        client_id = request.POST.get('client_id')
        plan_id = request.POST.get('plan_id')
        amount = request.POST.get('amount')
        transaction_id = request.POST.get('transaction_id')
        payment_method = request.POST.get('payment_method')
        is_renewal = request.POST.get('is_renewal') == 'on'

        try:
            client = Clients.objects.get(id=client_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            payment.client = client
            payment.plan = plan
            payment.amount = amount
            payment.transaction_id = transaction_id
            payment.payment_method = payment_method
            payment.is_renewal = is_renewal
            payment.save()
            
            messages.success(request, f"Payment updated for {client.name}")
            return redirect('payments')
            
        except (Clients.DoesNotExist, SubscriptionPlan.DoesNotExist):
            messages.error(request, "Invalid Client or Plan selected.")
            return redirect('payment-update', id=id)

from core.models import AdminExpense

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminExpenseListView(View):
    def get(self, request):
        expenses = AdminExpense.objects.filter(is_active=True).order_by('-date', '-id')
        return render(request, 'admin/expenses/list.html', {'expenses': expenses})

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminExpenseCreateView(View):
    def get(self, request):
        return render(request, 'admin/expenses/create.html')

    def post(self, request):
        title = request.POST.get('title')
        amount = request.POST.get('amount')
        remark = request.POST.get('remark')

        AdminExpense.objects.create(
            title=title,
            amount=amount,
            remark=remark
        )
        messages.success(request, "Expense created successfully.")
        return redirect('admin-expenses')

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminExpenseUpdateView(View):
    def get(self, request, id):
        expense = get_object_or_404(AdminExpense, id=id)
        return render(request, 'admin/expenses/create.html', {'expense': expense})

    def post(self, request, id):
        expense = get_object_or_404(AdminExpense, id=id)
        expense.title = request.POST.get('title')
        expense.amount = request.POST.get('amount')
        expense.remark = request.POST.get('remark')
        expense.save()

        messages.success(request, "Expense updated successfully.")
        return redirect('admin-expenses')

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminExpenseDeleteView(View):
    def post(self, request, id):
        expense = get_object_or_404(AdminExpense, id=id)
        expense.soft_delete()
        messages.success(request, "Expense moved to recycle bin.")
        return redirect('admin-expenses')


@method_decorator([login_required, staff_member_required, admin_action_required], name='dispatch')
class AdminRecycleBinView(View):
    def get(self, request):
        categories = []
        
        # AdminExpense
        expense_count = AdminExpense.objects.filter(is_active=False, deleted_at__isnull=False).count()
        if expense_count > 0:
            categories.append({
                'label': 'Expense',
                'model_name': 'AdminExpense',
                'count': expense_count,
                'icon': 'receipt',
            })
        
        # Clients (soft-deleted via is_active=False)
        client_count = Clients.objects.filter(is_active=False).count()
        if client_count > 0:
            categories.append({
                'label': 'Client',
                'model_name': 'Clients',
                'count': client_count,
                'icon': 'users',
            })
        
        return render(request, 'admin/recycle_bin/dashboard.html', {'categories': categories})


@method_decorator([login_required, staff_member_required, admin_action_required], name='dispatch')
class AdminRecycleBinListView(View):
    def get(self, request, model_name):
        from django.apps import apps
        
        id_field_map = {
            'AdminExpense': ('Expense', 'title'),
            'Clients': ('Client', 'clientId'),
        }
        
        label, id_field = id_field_map.get(model_name, (model_name, 'id'))
        model = apps.get_model('core', model_name)
        
        if model_name == 'Clients':
            items_query = model.objects.filter(is_active=False).order_by('-id')
        else:
            items_query = model.objects.filter(is_active=False, deleted_at__isnull=False).order_by('-deleted_at')
        
        deleted_items = []
        for item in items_query:
            display_id = getattr(item, id_field, None) or f"{label}-{item.id}"
            name = getattr(item, 'name', None) or getattr(item, 'title', None) or label
            deleted_at = getattr(item, 'deleted_at', None)
            
            deleted_items.append({
                'id': item.id,
                'display_id': display_id,
                'name': name,
                'deleted_at': deleted_at,
            })
        
        return render(request, 'admin/recycle_bin/list.html', {
            'items': deleted_items,
            'label': label,
            'model_name': model_name,
        })


@method_decorator([login_required, staff_member_required, admin_action_required], name='dispatch')
class AdminRestoreView(View):
    def post(self, request, model_name, pk):
        from django.apps import apps
        model = apps.get_model('core', model_name)
        item = get_object_or_404(model, id=pk)
        
        item.is_active = True
        item.deleted_at = None
        
        # For Clients, also reactivate their user account and handle clientId conflicts
        if model_name == 'Clients':
            # Check if an active client with the same clientId already exists
            if model.objects.filter(is_active=True, clientId=item.clientId).exclude(id=item.id).exists():
                item.clientId = last_client_id()
                
            if hasattr(item, 'user') and item.user:
                item.user.is_active = True
                item.user.save()
        
        item.save()
        return JsonResponse({'status': 'success', 'message': 'Item restored successfully'})


@method_decorator([login_required, staff_member_required, admin_action_required], name='dispatch')
class AdminPermanentDeleteView(View):
    def post(self, request, model_name, pk):
        from django.apps import apps
        model = apps.get_model('core', model_name)
        item = get_object_or_404(model, id=pk)
        
        # For Clients, also delete their user account
        if model_name == 'Clients' and hasattr(item, 'user') and item.user:
            item.user.delete()
        
        item.delete()
        return JsonResponse({'status': 'success', 'message': 'Item permanently deleted'})
