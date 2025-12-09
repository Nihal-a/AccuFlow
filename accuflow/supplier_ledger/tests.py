from django.test import TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from core.models import Clients as ClientModel, Suppliers, Purchases, Sales, Godowns
from supplier_ledger.views import SupplierLedgerView
from datetime import date, timedelta

User = get_user_model()

class SupplierLedgerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        
        self.client_obj = ClientModel.objects.create(name="Test Client", user=self.user)
        
        self.supplier = Suppliers.objects.create(name="Test Supplier", client=self.client_obj, is_active=True)
        
        self.godown = Godowns.objects.create(name="Test Godown", client=self.client_obj, is_active=True)
        
        self.factory = RequestFactory()
        
    def test_opening_balance_calculation(self):
        yesterday = date.today() - timedelta(days=1)
        
        Purchases.objects.create(
            purchase_no="P001", 
            supplier=self.supplier, 
            client=self.client_obj, 
            date=yesterday, 
            total_amount=1000, 
            is_active=True,
            godown=self.godown, 
            amount=1000,
            qty=1
        )
        
        Sales.objects.create(
            sale_no="S001", 
            supplier=self.supplier, 
            client=self.client_obj, 
            date=yesterday, 
            total_amount=200, 
            is_active=True,
            godown=self.godown,
            amount=200,
            qty=1
        )
        
        view = SupplierLedgerView()
        ob = view.calculate_opening_balance(self.supplier, self.client_obj, date.today())
        self.assertEqual(ob, -800)
        
    def test_view_post_integration(self):
        self.client.force_login(self.user)
        today_str = str(date.today())
        response = self.client.post('/supplierledger/', {
            'supplier': self.supplier.id,
            'dateFrom': today_str,
            'dateTo': today_str,
            'opening': 'off',
            'sort': 'Serial'
        })
        self.assertEqual(response.status_code, 200)

    def test_view_without_opening_balance(self):
        """Test that opening balance is 0 when 'opening' checkbox is checked (on)."""
        self.client.force_login(self.user)
        today_str = str(date.today())
        
        self.supplier.open_debit = 5000
        self.supplier.save()
        
        response = self.client.post('/supplierledger/', {
            'supplier': self.supplier.id,
            'dateFrom': today_str,
            'dateTo': today_str,
            'opening': 'on', # Checkbox Checked
            'sort': 'Serial'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['open_balance'], 0)
