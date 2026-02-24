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

logger = logging.getLogger(__name__)

@method_decorator([login_required, staff_member_required], name='dispatch')
class ClientsView(View):
    def get(self, request):
        clients = Clients.objects.filter(is_active=True).select_related('user')
        return render(request, 'admin/clients/clients.html', {'clients': clients})
    


@method_decorator([login_required, staff_member_required], name='dispatch')
class ClientAddView(View):
    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return render(request, 'admin/clients/create.html', {'plans': plans})

    def post(self, request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        wa = request.POST.get('wa')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('create-clients')

        if UserAccount.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('create-clients')

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('create-clients')

        user = UserAccount.objects.create_client(
            username=username,
            password=password,
        )
        client = Clients.objects.create(
            name=name,
            phone=phone,
            email=email,
            user=user,
            wa = wa,
            is_active=True,
            clientId = last_client_id()
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
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        user = client.user
        
        if password and password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('update-client', client_id=client.id)

        if UserAccount.objects.exclude(id=user.id).filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('update-client', client_id=client.id)

        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
                return redirect('update-client', client_id=client.id)

        client.name = name
        client.email = email
        client.phone = phone
        client.country_code = country_code


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
        client.is_active = False 
        client.user.is_active = False
        client.user.save()
        client.save()
        return redirect('clients')



def last_client_id():
    last_client = Clients.objects.filter(is_active=True, clientId__regex=r'^AF-\d+$').order_by('clientId').last() 
    if last_client and last_client.clientId:
        try:
            prefix, num = last_client.clientId.split('-')
            if not num.isdigit():
                return 'AF-1'
            return f"{prefix}-{int(num) + 1}"
        except ValueError:
            return 'AF-1'
    return 'AF-1'




@login_required
@staff_member_required
def check_username_availability(request):
    if request.method == 'POST':
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

from core.models import SubscriptionPayment, CompanyDetail, SupportContact

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

        try:
            client = Clients.objects.get(id=client_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)
            
            SubscriptionPayment.objects.create(
                client=client,
                plan=plan,
                amount=amount,
                transaction_id=transaction_id,
                payment_method=payment_method
            )
            
            messages.success(request, f"Payment recorded for {client.name}")
            return redirect('payments')
            
        except (Clients.DoesNotExist, SubscriptionPlan.DoesNotExist):
            messages.error(request, "Invalid Client or Plan selected.")
            return redirect('payment-create')

@method_decorator([login_required, staff_member_required], name='dispatch')
class CompanyUpdateView(View):
    def get(self, request):
        company = CompanyDetail.objects.first()
        return render(request, 'admin/company/profile.html', {'company': company})

    def post(self, request):
        company = CompanyDetail.objects.first()
        if not company:
            company = CompanyDetail.objects.create()
        
        company.name = request.POST.get('name')
        company.description = request.POST.get('description')
        company.address = request.POST.get('address')
        company.website = request.POST.get('website')
        
        if request.FILES.get('logo'):
            company.logo = request.FILES.get('logo')
            
        company.save()
        messages.success(request, "Company profile updated successfully.")
        return redirect('company_update')

@method_decorator([login_required, staff_member_required], name='dispatch')
class SupportContactListView(View):
    def get(self, request):
        contacts = SupportContact.objects.all().select_related('company')
        return render(request, 'admin/company/contact_list.html', {'contacts': contacts})

@method_decorator([login_required, staff_member_required], name='dispatch')
class SupportContactCreateView(View):
    def get(self, request):
        return render(request, 'admin/company/contact_form.html')

    def post(self, request):
        company = CompanyDetail.objects.first()
        if not company:
            company = CompanyDetail.objects.create()
            
        title = request.POST.get('title')
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        is_active = request.POST.get('is_active') == 'on'

        SupportContact.objects.create(
            company=company,
            title=title,
            name=name,
            email=email,
            phone=phone,
            is_active=is_active
        )
        messages.success(request, "Support contact added.")
        return redirect('contact_list')

@method_decorator([login_required, staff_member_required], name='dispatch')
class SupportContactUpdateView(View):
    def get(self, request, id):
        contact = get_object_or_404(SupportContact, id=id)
        return render(request, 'admin/company/contact_form.html', {'contact': contact})

    def post(self, request, id):
        contact = get_object_or_404(SupportContact, id=id)
        contact.title = request.POST.get('title')
        contact.name = request.POST.get('name')
        contact.email = request.POST.get('email')
        contact.phone = request.POST.get('phone')
        contact.is_active = request.POST.get('is_active') == 'on'
        contact.save()
        messages.success(request, "Support contact updated.")
        return redirect('contact_list')

@method_decorator([login_required, staff_member_required], name='dispatch')
class SupportContactDeleteView(View):
    def post(self, request, id):
        contact = get_object_or_404(SupportContact, id=id)
        contact.delete()
        messages.success(request, "Support contact deleted.")
        return redirect('contact_list')