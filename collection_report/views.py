from django.shortcuts import render
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from datetime import datetime
from decimal import Decimal
from core.models import Collection, Collectors
from core.views import getClient

class CollectionReportView(View):
    def get(self, request):
        return self.process_report(request)

    def post(self, request):
        return self.process_report(request)

    def process_report(self, request):
        client = getClient(request.user)
        date_from_str = request.POST.get("dateFrom")
        date_to_str = request.POST.get("dateTo")
        collector_id = request.POST.get("collector", "all")
        status = request.POST.get("status", "all")
        
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        if date_from_str and date_to_str:
            base_filter = Q(client=client)
            base_filter &= Q(date__gte=date_from_str)
            base_filter &= Q(date__lte=date_to_str)
            
            if collector_id and collector_id != "all":
                base_filter &= Q(collector_id=collector_id)
                
            if status and status != "all":
                base_filter &= Q(status=status)
            
            collections = Collection.objects.filter(base_filter).order_by('-date')
            total_amount = collections.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.0000')
            
            paginator = Paginator(collections, 50)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            collections_list = page_obj.object_list
        else:
            collections_list = []
            page_obj = None
            total_amount = Decimal('0.0000')

        context = {
            'collections': collections_list,
            'page_obj': page_obj,
            'collectors': collectors,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'collector_id': str(collector_id) if collector_id else 'all',
            'status': status,
            'total_amount': total_amount
        }
        return render(request, 'collection_report/collection_report.html', context)
