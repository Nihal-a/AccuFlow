from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import Collectors, Collection
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class CollectorCollectionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/collections.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_collector

    def get(self, request):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collections = Collection.objects.filter(collector=collector).order_by('-date')
        except Collectors.DoesNotExist:
            collector = None
            collections = []

        context = {
            'collections': collections,
            'collector': collector,
            'is_collector_view': True 
        }
        return render(request, self.template_name, context)

class CollectorCollectionDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'collector_view/collection_detail.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_collector

    def get(self, request, id):
        try:
            collector = Collectors.objects.get(user=request.user, is_active=True)
            collection = get_object_or_404(Collection, id=id, collector=collector)
        except Collectors.DoesNotExist:
            return render(request, '404.html', status=404)

        items = collection.items.all()
        
        context = {
            'collection': collection,
            'items': items,
        }
        return render(request, self.template_name, context)
