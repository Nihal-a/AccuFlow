"""
Tests for suppliers module authorization fixes.
Verifies that IDOR vulnerability is properly fixed.
"""

from django.test import TestCase, Client as HttpClient
from django.contrib.auth.hashers import make_password

from core.models import Clients, Suppliers, UserAccount


class SuppliersAuthorizationTests(TestCase):
    """Test that suppliers module enforces proper authorization."""
    
    def setUp(self):
        """Create test clients and suppliers."""
        # Client A
        self.user_a = UserAccount.objects.create(
            username='client_a',
            password=make_password('password123'),
            is_client=True
        )
        self.client_a = Clients.objects.create(
            name='Company A',
            email='a@example.com',
            user=self.user_a,
            clientId='A-001'
        )
        
        # Client B
        self.user_b = UserAccount.objects.create(
            username='client_b',
            password=make_password('password123'),
            is_client=True
        )
        self.client_b = Clients.objects.create(
            name='Company B',
            email='b@example.com',
            user=self.user_b,
            clientId='B-001'
        )
        
        # Create suppliers
        self.supplier_a = Suppliers.objects.create(
            name='Supplier A1',
            supplierId='SA-001',
            client=self.client_a,
            balance=1000.0
        )
        
        self.supplier_b = Suppliers.objects.create(
            name='Supplier B1',
            supplierId='SB-001',
            client=self.client_b,
            balance=2000.0
        )
        
        self.http_client = HttpClient()
    
    def test_delete_supplier_same_client_allowed(self):
        """User can delete their own supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/suppliers/delete/{self.supplier_a.id}/')
        
        self.assertEqual(response.status_code, 302)
        
        self.supplier_a.refresh_from_db()
        self.assertFalse(self.supplier_a.is_active)
    
    def test_delete_supplier_cross_tenant_blocked(self):
        """User CANNOT delete another tenant's supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/suppliers/delete/{self.supplier_b.id}/')
        
        self.assertEqual(response.status_code, 404)
        
        self.supplier_b.refresh_from_db()
        self.assertTrue(self.supplier_b.is_active)
    
    def test_update_supplier_view_same_client_allowed(self):
        """User can view update form for their own supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/suppliers/update/{self.supplier_a.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Supplier A1')
    
    def test_update_supplier_view_cross_tenant_blocked(self):
        """User CANNOT view update form for another tenant's supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/suppliers/update/{self.supplier_b.id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_update_supplier_post_same_client_allowed(self):
        """User can update their own supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.post(
            f'/suppliers/update/{self.supplier_a.id}/',
            {
                'name': 'Updated Supplier A1',
                'phone': '1234567890',
                'address': 'New Address',
                'open_credit': 0,
                'open_debit': 0,
                'otc_credit': 0,
                'otc_debit': 0,
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        self.supplier_a.refresh_from_db()
        self.assertEqual(self.supplier_a.name, 'Updated Supplier A1')
    
    def test_update_supplier_post_cross_tenant_blocked(self):
        """User CANNOT update another tenant's supplier."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.post(
            f'/suppliers/update/{self.supplier_b.id}/',
            {
                'name': 'Hacked Supplier B1',
                'phone': '1234567890',
                'address': 'Hacker Address',
                'open_credit': 0,
                'open_debit': 0,
                'otc_credit': 0,
                'otc_debit': 0,
            }
        )
        
        self.assertEqual(response.status_code, 404)
        
        self.supplier_b.refresh_from_db()
        self.assertEqual(self.supplier_b.name, 'Supplier B1')
    
    def test_superuser_cross_tenant_access(self):
        """Superuser can access all suppliers."""
        superuser = UserAccount.objects.create(
            username='admin',
            password=make_password('admin123'),
            is_superuser=True,
            is_client=True
        )
        admin_client = Clients.objects.create(
            name='Admin',
            email='admin@example.com',
            user=superuser,
            clientId='ADMIN'
        )
        
        self.http_client.force_login(superuser)
        
        response_a = self.http_client.get(f'/suppliers/update/{self.supplier_a.id}/')
        self.assertEqual(response_a.status_code, 200)
        
        response_b = self.http_client.get(f'/suppliers/update/{self.supplier_b.id}/')
        self.assertEqual(response_b.status_code, 200)
