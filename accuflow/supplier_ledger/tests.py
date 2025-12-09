from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from core.models import Clients as Client, Suppliers, Purchases, Sales, Godowns
from supplier_ledger.views import SupplierLedgerView
from datetime import date, timedelta

User = get_user_model()

class SupplierLedgerTest(TestCase):
    def setUp(self):
        # Create UserAccount
        self.user = User.objects.create_user(username='testuser', password='password')
        
        # Create Client
        self.client = Client.objects.create(name="Test Client", user=self.user)
        
        # Create Supplier
        self.supplier = Suppliers.objects.create(name="Test Supplier", client=self.client, is_active=True)
        
        # Create Godown (required by model usually)
        self.godown = Godowns.objects.create(name="Test Godown", client=self.client, is_active=True)
        
        self.factory = RequestFactory()
        
    def test_opening_balance_calculation(self):
        # Create past transactions (before today)
        yesterday = date.today() - timedelta(days=1)
        
        # Purchase (Credit -)
        Purchases.objects.create(
            purchase_no="P001", 
            supplier=self.supplier, 
            client=self.client, 
            date=yesterday, 
            total_amount=1000, 
            is_active=True,
            godown=self.godown, # Correct field name usually 'godown' FK
            amount=1000,
            qty=1
        )
        
        # Sale (Return) (Debit +)
        Sales.objects.create(
            sale_no="S001", 
            supplier=self.supplier, 
            client=self.client, 
            date=yesterday, 
            total_amount=200, 
            is_active=True,
            godown=self.godown,
            amount=200,
            qty=1
        )
        
        view = SupplierLedgerView()
        # OB = Sales - Purchases = 200 - 1000 = -800
        ob = view.calculate_opening_balance(self.supplier, self.client, date.today())
        self.assertEqual(ob, -800)
        
    def test_view_post_integration(self):
        # Basic integration test for POST
        today_str = str(date.today())
        request = self.factory.post('/supplier-ledger/', {
            'supplier': self.supplier.id,
            'dateFrom': today_str,
            'dateTo': today_str,
            'opening': 'off',
            'sort': 'Serial'
        })
        request.user = self.user
        
        view = SupplierLedgerView()
        response = view.post(request)
        
        self.assertEqual(response.status_code, 200)
        # Verify context details?
        # Since we rendered response, response.content would contain HTML.
        # We can check if status 200 is returned.
