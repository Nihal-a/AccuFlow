from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_url = reverse('login')
        clients_url = reverse('clients')

        exempt_paths = [
            login_url,
            '/logout/',
            '/django-admin/',
            '/landing/',
            '/subscription-expired/',
        ]

        if getattr(settings, 'STATIC_URL', None):
            exempt_paths.append(settings.STATIC_URL)
        if getattr(settings, 'MEDIA_URL', None):
            exempt_paths.append(settings.MEDIA_URL)

        if not request.user.is_authenticated:
            if not any(request.path.startswith(path) for path in exempt_paths):
                return redirect(f"{login_url}?next={request.path}")

        if request.user.is_authenticated and request.user.is_admin:
            if (
                not any(request.path.startswith(path) for path in exempt_paths)
                and not request.path.startswith('/admin/')
            ):
                return redirect(clients_url)

        return self.get_response(request)
