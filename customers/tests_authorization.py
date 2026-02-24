"""
Tests for customers module authorization fixes.
Verifies that IDOR vulnerability is properly fixed.
"""

from django.test import TestCase, Client as HttpClient
from django.contrib.auth.hashers import make_password
from django.urls import reverse

from core.models import Clients, Customers, UserAccount
from core.views import getClient


class CustomersAuthorizationTests(TestCase):
    """Test that customers module enforces proper authorization."""
    
    def setUp(self):
        """Create test clients and customers."""
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
        
        # Create customers
        self.customer_a = Customers.objects.create(
            name='Customer A1',
            customerId='CA-001',
            client=self.client_a,
            balance=1000.0
        )
        
        self.customer_b = Customers.objects.create(
            name='Customer B1',
            customerId='CB-001',
            client=self.client_b,
            balance=2000.0
        )
        
        self.http_client = HttpClient()
    
    def test_delete_customer_same_client_allowed(self):
        """User can delete their own customer."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/customers/delete/{self.customer_a.id}/')
        
        # Should redirect to customers list
        self.assertEqual(response.status_code, 302)
        
        # Verify customer is soft-deleted
        self.customer_a.refresh_from_db()
        self.assertFalse(self.customer_a.is_active)
    
    def test_delete_customer_cross_tenant_blocked(self):
        """User CANNOT delete another tenant's customer."""
        self.http_client.force_login(self.user_a)
        
        # Try to delete Customer B
        response = self.http_client.get(f'/customers/delete/{self.customer_b.id}/')
        
        # Should return 404 (object not found for this client)
        self.assertEqual(response.status_code, 404)
        
        # Verify Customer B still active
        self.customer_b.refresh_from_db()
        self.assertTrue(self.customer_b.is_active)
    
    def test_update_customer_view_same_client_allowed(self):
        """User can view update form for their own customer."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/customers/update/{self.customer_a.id}/')
        
        # Should display update form
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Customer A1')
    
    def test_update_customer_view_cross_tenant_blocked(self):
        """User CANNOT view update form for another tenant's customer."""
        self.http_client.force_login(self.user_a)
        
        # Try to view Customer B's update form
        response = self.http_client.get(f'/customers/update/{self.customer_b.id}/')
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
    
    def test_update_customer_post_same_client_allowed(self):
        """User can update their own customer."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.post(
            f'/customers/update/{self.customer_a.id}/',
            {
                'name': 'Updated Customer A1',
                'phone': '1234567890',
                'address': 'New Address',
                'open_credit': 0,
                'open_debit': 0,
                'otc_credit': 0,
                'otc_debit': 0,
            }
        )
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify update
        self.customer_a.refresh_from_db()
        self.assertEqual(self.customer_a.name, 'Updated Customer A1')
    
    def test_update_customer_post_cross_tenant_blocked(self):
        """User CANNOT update another tenant's customer."""
        self.http_client.force_login(self.user_a)
        
        # Try to update Customer B
        response = self.http_client.post(
            f'/customers/update/{self.customer_b.id}/',
            {
                'name': 'Hacked Customer B1',
                'phone': '1234567890',
                'address': 'Hacker Address',
                'open_credit': 0,
                'open_debit': 0,
                'otc_credit': 0,
                'otc_debit': 0,
            }
        )
        
        # Should return 404
        self.assertEqual(response.status_code, 404)
        
        # Verify Customer B unchanged
        self.customer_b.refresh_from_db()
        self.assertEqual(self.customer_b.name, 'Customer B1')
    
    def test_superuser_cross_tenant_access(self):
        """Superuser can access all customers."""
        # Create superuser
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
        
        # Should access Customer A
        response_a = self.http_client.get(f'/customers/update/{self.customer_a.id}/')
        self.assertEqual(response_a.status_code, 200)
        
        # Should access Customer B
        response_b = self.http_client.get(f'/customers/update/{self.customer_b.id}/')
        self.assertEqual(response_b.status_code, 200)
