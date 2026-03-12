from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

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
                # Validate the next URL to prevent open redirect attacks
                next_url = request.path
                if url_has_allowed_host_and_scheme(next_url, allowed_hosts=settings.ALLOWED_HOSTS):
                    return redirect(f"{login_url}?next={next_url}")
                return redirect(login_url)

        if request.user.is_authenticated and request.user.is_admin:
            if (
                not any(request.path.startswith(path) for path in exempt_paths)
                and not request.path.startswith('/admin/')
                and not request.path.startswith('/api/')
                and not request.path.startswith('/changepass/')
                and not request.path.startswith('/recycle-bin/')
            ):
                return redirect(clients_url)

        return self.get_response(request)
