from django.shortcuts import render,redirect, get_object_or_404
from core.models import Collectors, UserAccount
from django.views import View
from django.views.generic.edit import DeleteView
from django.contrib import messages

from core.views import getClient

class CollectorView(View):
    def get(self,request):
        collector = Collectors.objects.filter(is_active=True,client=getClient(request.user))
        return render(request,'collector/collectors.html',{'collectors':collector})


class AddCollectorView(View):
    def get(self,request):
        return render(request,'collector/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
             messages.error(request, "Passwords do not match.")
             return redirect('create-collector')
        
        if UserAccount.objects.filter(username=username).exists():
             messages.error(request, "Username already exists.")
             return redirect('create-collector')

        try:
            user = UserAccount.objects.create_collector(
                username=username,
                password=password
            )
            
            collector = Collectors.objects.create(
                name=name,
                phone=phone,
                address=address,
                client=getClient(request.user),
                user=user
            )
            if wa:
                collector.country_code = country_code
                collector.wa = wa
                collector.save()
                
            messages.success(request, f"Collector '{name}' created successfully.")
            return redirect('collectors')
        except Exception as e:
            messages.error(request, f"Error creating collector: {str(e)}")
            return redirect('create-collector')

class DeleteCollectorView(View):
    def get(self, request, collector_id):
        collector = get_object_or_404(Collectors, id=collector_id)
        collector.is_active = False 
        collector.save()
        return redirect('collectors')
 

class UpdateCollectorView(View):
    def get(self, request, collector_id):
        collector = get_object_or_404(Collectors, id=collector_id)
        return render(request, 'collector/update.html', {'collector': collector})

    def post(self, request, collector_id):
        collector = get_object_or_404(Collectors, id=collector_id)
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        country_code = request.POST.get('country_code')
        wa = request.POST.get('whatsapp_number')
        
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        user = collector.user
        
        if not user and username and password:
            if password != confirm_password:
                 messages.error(request, "Passwords do not match.")
                 return redirect('edit-collector', collector_id=collector_id)
            
            if UserAccount.objects.filter(username=username).exists():
                 messages.error(request, "Username already exists.")
                 return redirect('edit-collector', collector_id=collector_id)
            
            try:
                user = UserAccount.objects.create_collector(username=username, password=password)
                collector.user = user
            except Exception as e:
                messages.error(request, f"Error creating user: {e}")
                return redirect('edit-collector', collector_id=collector_id)
        
        elif user:
            if password and password != confirm_password:
                 messages.error(request, "Passwords do not match.")
                 return redirect('edit-collector', collector_id=collector_id)
            
            if username and username != user.username:
                 if UserAccount.objects.exclude(id=user.id).filter(username=username).exists():
                     messages.error(request, "Username already exists.")
                     return redirect('edit-collector', collector_id=collector_id)
                 user.username = username
            
            if password:
                from django.contrib.auth.hashers import make_password
                user.password = make_password(password)
                
            user.save()

        collector.name = name
        collector.phone = phone
        collector.address = address
        if wa:
            collector.country_code = country_code
            collector.wa = wa
        collector.save()
        
        messages.success(request, f"Collector '{name}' updated successfully.")
        return redirect('collectors')