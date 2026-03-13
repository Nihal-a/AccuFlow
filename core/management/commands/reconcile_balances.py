import csv
import sys
from decimal import Decimal
from django.core.management.base import BaseCommand
from core.models import Customers, Suppliers, Godowns, CashBanks, Clients
from core.views import calculate_customer_balance, calculate_supplier_balance, calculate_cashbank_balance

class Command(BaseCommand):
    help = 'Reconciles party balances and stock quantities'

    def handle(self, *args, **options):
        clients = Clients.objects.filter(is_active=True)
        discrepancies = []

        for client in clients:
            self.stdout.write(f"Checking client: {client.name}")

            # Customers
            customers = Customers.objects.filter(client=client, is_active=True)
            for c in customers:
                calc = calculate_customer_balance(c, client)
                if Decimal(str(c.balance)) != Decimal(str(calc)):
                    discrepancies.append(f"Customer {c.name} ({c.id}): DB={c.balance}, Calc={calc}")

            # Suppliers
            suppliers = Suppliers.objects.filter(client=client, is_active=True)
            for s in suppliers:
                calc = calculate_supplier_balance(s, client)
                if Decimal(str(s.balance)) != Decimal(str(calc)):
                    discrepancies.append(f"Supplier {s.name} ({s.id}): DB={s.balance}, Calc={calc}")

            # Godowns (Qty)
            godowns = Godowns.objects.filter(client=client, is_active=True)
            from core.services import FinancialService
            for g in godowns:
                calc = FinancialService.calculate_godown_qty(g, client)
                if Decimal(str(g.qty)) != Decimal(str(calc)):
                    discrepancies.append(f"Godown {g.name} ({g.id}): DB={g.qty}, Calc={calc}")

            # CashBanks
            cashbanks = CashBanks.objects.filter(client=client, is_active=True)
            for cb in cashbanks:
                calc = calculate_cashbank_balance(cb, client)
                if Decimal(str(cb.balance)) != Decimal(str(calc)):
                    discrepancies.append(f"CashBank {cb.name} ({cb.id}): DB={cb.balance}, Calc={calc}")
        
        if discrepancies:
            for d in discrepancies:
                self.stdout.write(self.style.ERROR(d))
        else:
            self.stdout.write(self.style.SUCCESS("All balances reconciled successfully!"))
