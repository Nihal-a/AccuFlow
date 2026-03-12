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
            except Exception:
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
                    client_obj = Clients.objects.get(user=request.user, is_active=True)
                except Clients.DoesNotExist:
                    pass
            elif request.user.is_collector:
                try:
                    collector = Collectors.objects.get(user=request.user, is_active=True)
                    client_obj = collector.client
                except (Collectors.DoesNotExist, AttributeError):
                    pass

            # Check subscription status
            # If they are NOT an admin, they MUST have an active subscription if they are intended to be a client or collector.
            if not request.user.is_admin:
                is_active = True
                if client_obj:
                    if not client_obj.is_subscription_active:
                        is_active = False
                elif request.user.is_client or request.user.is_collector:
                    # Authenticated as client/collector but no associated client object found
                    is_active = False
                
                if not is_active:
                    try:
                        expired_url = reverse('subscription_expired')
                    except Exception:
                        expired_url = '/subscription-expired/'
                    
                    # Handle AJAX requests separately to avoid returning HTML instead of expected JSON
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                        from django.http import HttpResponseForbidden
                        return HttpResponseForbidden("Subscription Expired. Please renew your subscription.")
                        
                    # For regular requests, redirect to expired screen
                    return redirect(expired_url)

        return self.get_response(request)

class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            session_key = request.session.session_key
            
            # If the user has a session key and it doesn't match the current one, logout.
            # We don't block if last_session_key is None (e.g. initial setup)
            if request.user.last_session_key and request.user.last_session_key != session_key:
                # To prevent redirect loop, check if we are already at login or logout
                if not any(request.path.startswith(p) for p in [reverse('login'), reverse('logout'), '/static/', '/media/']):
                    logout(request)
                    messages.error(request, "Multiple logins detected. You have been logged out from this session because you logged in from another device.")
                    return redirect('login')
                    
        return self.get_response(request)

class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Add CSP Headers 
        response['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https: http:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https: http:; style-src 'self' 'unsafe-inline' https: http:; font-src 'self' data: https: http:; img-src 'self' data: blob: https: http:; connect-src 'self' ws: wss: https: http:;"
        return response
