from core.models import Collection, CompanyDetail

def company_info(request):
    try:
        company = CompanyDetail.objects.prefetch_related('contacts').first()
        if company:
            active_contacts = company.contacts.filter(is_active=True)
            return {
                'company_details': company,
                'support_contacts': active_contacts
            }
    except:
        pass
    return {'company_details': None, 'support_contacts': []}
from core.views import getClient

from django.utils import timezone
from datetime import timedelta

def notifications(request):
    notifications_data = {
        'pending_notifs': [],
        'subscription_alert': None
    }
    
    if not request.user.is_authenticated:
        return notifications_data
        
    try:
        client = getClient(request.user)
        if not client and request.user.is_collector:
            collector = request.user.collectors_set.first()
            if collector:
                client = collector.client

        if client:
             # Pending approvals
             pending = Collection.objects.filter(client=client, status='Pending', is_viewed=False).order_by('-date')
             notifications_data['pending_notifs'] = list(pending)
             
             # Subscription alert (if within 7 days)
             if client.subscription_end:
                 today = timezone.now().date()
                 days_remaining = (client.subscription_end - today).days
                 if 0 <= days_remaining <= 7:
                     notifications_data['subscription_alert'] = {
                         'days': days_remaining,
                         'end_date': client.subscription_end,
                         'is_expired': False
                     }
                 elif days_remaining < 0:
                     notifications_data['subscription_alert'] = {
                         'days': days_remaining,
                         'end_date': client.subscription_end,
                         'is_expired': True
                     }
        elif request.user.is_superuser:
             pending = Collection.objects.filter(status='Pending', is_viewed=False).order_by('-date')
             notifications_data['pending_notifs'] = list(pending)
             
    except Exception as e:
        print(f"Notification processor error: {e}")
        
    return notifications_data
