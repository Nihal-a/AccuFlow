from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Clients, Suppliers, Customers
from core.views import update_party, update_ledger

User = get_user_model()

class LedgerLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Clients.objects.create(name="Test Client", user=self.user)
        self.supplier = Suppliers.objects.create(name="Test Supplier", client=self.client, is_active=True)
        self.customer = Customers.objects.create(name="Test Customer", client=self.client, is_active=True)

    def test_update_party_netting(self):
        """Test that update_party nets off debit and credit."""
        self.supplier.credit = 100
        self.supplier.debit = 40
        update_party(self.supplier)
        self.assertEqual(self.supplier.credit, 60)
        self.assertEqual(self.supplier.debit, 0)
        self.assertEqual(self.supplier.balance, -60) # Balance = Debit - Credit

        self.supplier.credit = 30
        self.supplier.debit = 80
        update_party(self.supplier)
        self.assertEqual(self.supplier.credit, 0)
        self.assertEqual(self.supplier.debit, 50)
        self.assertEqual(self.supplier.balance, 50)

        self.supplier.credit = 50
        self.supplier.debit = 50
        update_party(self.supplier)
        self.assertEqual(self.supplier.credit, 0)
        self.assertEqual(self.supplier.debit, 0)
        self.assertEqual(self.supplier.balance, 0)

    def test_update_ledger_purchase(self):
        """Test update_ledger for Purchase (affecting 'where' i.e. Supplier)."""
        update_ledger(where=self.supplier, new_purchase=100)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.credit, 100)
        self.assertEqual(self.supplier.debit, 0)

        update_ledger(where=self.supplier, new_purchase=50)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.credit, 150)

        update_ledger(where=self.supplier, old_purchase=50, new_purchase=80)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.credit, 180)

        update_ledger(where=self.supplier, old_purchase=80, new_purchase=0)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.credit, 100)

    def test_update_ledger_sale(self):
        """Test update_ledger for Sale (affecting 'to' i.e. Customer)."""
        update_ledger(where=None, to=self.customer, new_sale=200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debit, 200)
        
        update_ledger(where=None, to=self.customer, old_sale=200, new_sale=150)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debit, 150)

    def test_update_ledger_flip_sign(self):
        """Test that reducing credit below 0 flips to debit, and vice versa."""
        self.supplier.credit = 50
        self.supplier.save()

        update_ledger(where=self.supplier, old_purchase=100)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.credit, 0)
        self.assertEqual(self.supplier.debit, 50)
        
        self.customer.debit = 50
        self.customer.save()
        
        update_ledger(where=None, to=self.customer, old_sale=100)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debit, 0)
        self.assertEqual(self.customer.credit, 50)
