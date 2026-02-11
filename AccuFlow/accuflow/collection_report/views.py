from django.shortcuts import render
from django.views import View
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
        collector_id = request.POST.get("collector")
        
        collectors = Collectors.objects.filter(is_active=True, client=client)
        
        base_filter = Q(client=client) # Assuming client filter applies to collections too. 
        # But Collection model has 'client' field too? Let's check model definition previously output.
        # Yes: client = models.ForeignKey(Clients...
        
        if date_from_str:
            base_filter &= Q(date__gte=date_from_str)
        if date_to_str:
            base_filter &= Q(date__lte=date_to_str)
        
        if collector_id:
            base_filter &= Q(collector_id=collector_id)
            
        # Maybe show only 'Approved' collections? Or all? Usually reports show final data, so Approved.
        # "it is same as view collection" - View Collection usually shows everything or handles status.
        # If it's a "Report" of "Collection", it usually means money collected.
        # Let's show all for now, maybe add status column if needed. 
        # But for 'Report' usually implies 'Done' deals. I will default to showing all but maybe sort by date.
        
        collections = Collection.objects.filter(base_filter).order_by('-date')
        
        total_amount = collections.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.0000')
        
        context = {
            'collections': collections,
            'collectors': collectors,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'collector_id': int(collector_id) if collector_id else '',
            'total_amount': total_amount
        }
        return render(request, 'collection_report/collection_report.html', context)
