from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from core.decorators import admin_action_required

@method_decorator([login_required, admin_action_required], name='dispatch')
class ChangePassView(View):
    def get(self, request):
        return render(request, 'change_pass/change_pass.html')
        
    def post(self, request):
        current_password = request.POST.get('currentpassword')
        new_password = request.POST.get('newpassword')
        confirm_password = request.POST.get('confirmpassword')
        
        user = request.user
        
        if not user.check_password(current_password):
            messages.error(request, 'Current password is not correct.')
            return redirect('changepass')
            
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('changepass')
            
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return redirect('changepass')
            
        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password was successfully updated!')
        return redirect('changepass')
