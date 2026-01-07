from core.models import Collection
from core.views import getClient

def notifications(request):
    notifications_data = {'pending_notifs': []}
    
    if not request.user.is_authenticated:
        return notifications_data
        
    try:
        client = getClient(request.user)
        if client:
             pending = Collection.objects.filter(client=client, status='Pending', is_viewed=False).order_by('-date')
             notifications_data['pending_notifs'] = pending
        elif request.user.is_superuser:
             # Fallback for Superuser without Client link: Show all pending
             pending = Collection.objects.filter(status='Pending', is_viewed=False).order_by('-date')
             notifications_data['pending_notifs'] = pending
    except Exception as e:
        pass
        
    return notifications_data
