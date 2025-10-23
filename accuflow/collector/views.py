from django.shortcuts import render,redirect, get_object_or_404
from core.models import Collectors
from django.views import View
from django.views.generic.edit import DeleteView

class CollectorView(View):
    def get(self,request):
        collector = Collectors.objects.filter(is_active=True)
        return render(request,'collector/collectors.html',{'collectors':collector})


class AddCollectorView(View):
    def get(self,request):
        return render(request,'collector/create.html')
    
    def post(self,request):
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        Collectors.objects.create(
            name=name,
            phone=phone,
            address=address,
        )
        return redirect('collectors')

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
        collector.name = request.POST.get('name')
        collector.phone = request.POST.get('phone')
        collector.address = request.POST.get('address')
        collector.save()
        return redirect('collectors')