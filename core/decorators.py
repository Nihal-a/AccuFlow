from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def admin_action_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Only enforce secret authorization for staff (admin) users.
        # Regular clients/customers can access these features with just their normal login.
        if request.user.is_staff:
            if not request.session.get('admin_action_authorized'):
                messages.error(request, "Secret authentication required to access this feature.")
                return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
