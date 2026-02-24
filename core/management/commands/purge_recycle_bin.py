from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import (
    Customers, Suppliers, Expenses, Godowns, CashBanks, Collectors,
    Purchases, Sales, Commissions, NSDs, Cashs, StockTransfers, Collection
)

class Command(BaseCommand):
    help = 'Purges items from the recycle bin that are older than 30 days.'

    def handle(self, *args, **kwargs):
        cutoff_date = timezone.now() - timedelta(days=30)
        
        models_to_purge = [
            Customers, Suppliers, Expenses, Godowns, CashBanks, Collectors,
            Purchases, Sales, Commissions, NSDs, Cashs, StockTransfers, Collection
        ]
        
        total_purged = 0
        for model in models_to_purge:
            deleted_items = model.objects.filter(is_active=False, deleted_at__lt=cutoff_date)
            count = deleted_items.count()
            if count > 0:
                self.stdout.write(self.style.SUCCESS(f'Purging {count} {model.__name__} items...'))
                deleted_items.delete()
                total_purged += count
                
        self.stdout.write(self.style.SUCCESS(f'Successfully purged {total_purged} total items from recycle bin.'))
