
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash

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
            
        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password was successfully updated!')
        return redirect('changepass')
