import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Clients,UserAccount 
from django.views import View
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password

class ClientsView(View):
    def get(self, request):
        clients = Clients.objects.filter(is_active=True).select_related('user')
        return render(request, 'admin/clients/clients.html', {'clients': clients})
    


class ClientAddView(View):
    def get(self, request):
        return render(request, 'admin/clients/create.html')

    def post(self, request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        wa = request.POST.get('wa')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('create-clients')

        if UserAccount.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('create-clients')

        user = UserAccount.objects.create_client(
            username=username,
            password=password,
        )
        client = Clients.objects.create(
            name=name,
            phone=phone,
            email=email,
            user=user,
            wa = wa,
            is_active=True,
            clientId = last_client_id()
        )

        messages.success(request, f"Client '{name}' created successfully!")
        return redirect('clients')
    
    
class ClientUpdateView(View):
    def get(self,request,id):
        client = get_object_or_404(Clients, id=id, is_active=True)
        user = client.user
        context = {
            'client': client,
            'user': user,
        }
        return render(request, 'admin/clients/update.html', context)    
    def post(self,request,id):
        client = get_object_or_404(Clients, id=id, is_active=True)
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        wa = request.POST.get('wa')
        country_code = request.POST.get('country_code')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        user = client.user
        
        if password and password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('update-client', client_id=client.id)

        if UserAccount.objects.exclude(id=user.id).filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('update-client', client_id=client.id)

        client.name = name
        client.email = email
        client.phone = phone
        client.country_code = country_code
        client.save()

        user.username = username
        if password:
            user.password = make_password(password)
        user.save()

        messages.success(request, "Client updated successfully.")
        return redirect('clients')

        

class DeleteClientView(View):
    def get(self, request, client_id):
        client = get_object_or_404(Clients, id=client_id)
        client.is_active = False 
        client.user.is_active = False
        client.user.save()
        client.save()
        return redirect('clients')



def last_client_id():
    last_client = Clients.objects.filter(is_active=True).order_by('clientId').last() 
    if last_client and last_client.clientId != None:
        prefix, num = last_client.clientId.split('-')
        new_client_id = f"{prefix}-{int(num) + 1}"
    else: 
        
        new_client_id = 'AF-1'
    return new_client_id




def check_username_availability(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            username = data.get('username', '').strip()
            exists = UserAccount.objects.filter(username=username).exists()
            return JsonResponse({'available': not exists})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)