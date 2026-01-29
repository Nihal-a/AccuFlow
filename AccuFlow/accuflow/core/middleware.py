from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import logout
from .models import Clients, Collectors

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check authenticated users
        if request.user.is_authenticated:
            # Skip check for admins
            if request.user.is_admin:
                return self.get_response(request)

            # Define paths that are always allowed to prevent redirect loops
            try:
                login_url = reverse('login')
                logout_url = reverse('logout')
            except:
                login_url = '/login/'
                logout_url = '/logout/'

            allowed_paths = [
                login_url,
                logout_url,
                '/static/',
                '/media/',
                '/admin/', # Django admin
                '/subscription-expired/',
            ]

            # If current path is allowed, skip check
            if any(request.path.startswith(path) for path in allowed_paths):
                return self.get_response(request)

            # Identify client object
            client_obj = None
            if request.user.is_client:
                try:
                    client_obj = Clients.objects.get(user=request.user)
                except Clients.DoesNotExist:
                    pass
            elif request.user.is_collector:
                try:
                    collector = Collectors.objects.get(user=request.user)
                    client_obj = collector.client
                except (Collectors.DoesNotExist, AttributeError):
                    pass

            # Check subscription status
            if client_obj:
                if not client_obj.is_subscription_active:
                    # Redirect to subscription expired page WITHOUT logging out
                    try:
                        expired_url = reverse('subscription_expired')
                    except:
                        expired_url = '/subscription-expired/'
                    return redirect(expired_url)

        return self.get_response(request)
