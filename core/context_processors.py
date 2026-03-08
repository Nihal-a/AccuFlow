from core.models import Collection, Clients


from core.views import getClient

from django.utils import timezone
from datetime import timedelta

def notifications(request):
    notifications_data = {
        'pending_notifs': [],
        'subscription_alert': None,
        'admin_subscription_alerts': []
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
             if request.user.is_collector:
                 collector = request.user.collectors_set.first()
                 if collector:
                     pending = Collection.objects.filter(collector=collector, status__in=['New', 'Approved', 'Rejected'], is_viewed=False).order_by('-date')
                     notifications_data['pending_notifs'] = list(pending)
             else:
                 pending = Collection.objects.filter(client=client, status='Pending', is_viewed=False).order_by('-date')
                 notifications_data['pending_notifs'] = list(pending)
             
             # Subscription alert (if within 7 days)
             if client.subscription_end:
                 today = timezone.now().date()
                 days_remaining = (client.subscription_end - today).days
                 notifications_data['days_remaining'] = days_remaining
                 
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
             
             today = timezone.now().date()
             threshold_date = today + timedelta(days=7)
             expiring_clients = Clients.objects.filter(
                 is_active=True,
                 subscription_end__lte=threshold_date,
                 subscription_end__gte=today - timedelta(days=30)
             ).order_by('subscription_end')
             
             admin_alerts = []
             for c in expiring_clients:
                 days_remaining = (c.subscription_end - today).days
                 admin_alerts.append({
                     'client': c,
                     'days': days_remaining,
                     'end_date': c.subscription_end,
                     'is_expired': days_remaining < 0
                 })
             notifications_data['admin_subscription_alerts'] = admin_alerts
             
    except Exception as e:
        pass
        
    return notifications_data
