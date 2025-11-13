from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Clients

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username,password=password)
        if user:
            login(request,user) 
            if user.is_admin:
                return redirect('clients')
            elif user.is_client:
                return redirect('customers')
            else:
                pass
        return redirect('login')
    return render(request, 'login.html') 


def user_logout(request):
    logout(request)    
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')
 

def getClient(user):
    if Clients.objects.filter(user=user,is_active=True).exists():
        return Clients.objects.get(user=user,is_active=True)
    else:
        return None