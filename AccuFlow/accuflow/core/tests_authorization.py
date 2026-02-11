"""
Authorization tests for multi-tenant access control.

Tests verify that the IDOR (Insecure Direct Object Reference) vulnerability
is properly fixed and users cannot access data from other tenants.

Test Coverage:
- Cross-tenant access blocked for regular users
- Same-tenant access allowed
- Superuser cross-tenant access allowed
- Authorization utilities work correctly
"""

from django.test import TestCase, Client as HttpClient
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.http import Http404

from core.models import (
    Clients, Customers, Suppliers, Collectors,
    UserAccount, Purchases, Sales, Cashs
)
from core.views import getClient
from core.authorization import (
    get_object_for_client,
    get_object_for_user,
    verify_object_ownership,
    check_superuser_access
)


class AuthorizationUtilityTests(TestCase):
    """Test authorization utility functions."""
    
    def setUp(self):
        """Create test clients and users."""
        # Client A with user
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
        
        # Client B with user
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
        
        # Superuser
        self.superuser = UserAccount.objects.create(
            username='admin',
            password=make_password('admin123'),
            is_superuser=True,
            is_client=True
        )
        self.superuser_client = Clients.objects.create(
            name='Admin Client',
            email='admin@example.com',
            user=self.superuser,
            clientId='ADMIN-001'
        )
        
        # Create test customers for each client
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
    
    def test_get_object_for_client_success(self):
        """Test successful retrieval of own client's object."""
        customer = get_object_for_client(
            Customers,
            self.client_a,
            id=self.customer_a.id
        )
        self.assertEqual(customer.id, self.customer_a.id)
        self.assertEqual(customer.name, 'Customer A1')
    
    def test_get_object_for_client_cross_tenant_blocked(self):
        """Test that cross-tenant access is blocked."""
        with self.assertRaises(Http404):
            # Client A trying to access Client B's customer
            get_object_for_client(
                Customers,
                self.client_a,
                id=self.customer_b.id
            )
    
    def test_get_object_for_user_success(self):
        """Test get_object_for_user with valid access."""
        customer = get_object_for_user(
            Customers,
            self.user_a,
            id=self.customer_a.id
        )
        self.assertEqual(customer.id, self.customer_a.id)
    
    def test_get_object_for_user_cross_tenant_blocked(self):
        """Test cross-tenant blocking with get_object_for_user."""
        with self.assertRaises(Http404):
            get_object_for_user(
                Customers,
                self.user_a,
                id=self.customer_b.id
            )
    
    def test_superuser_cross_tenant_access(self):
        """Test that superusers can access across tenants."""
        # Superuser accessing Client A's customer
        customer_a = get_object_for_user(
            Customers,
            self.superuser,
            id=self.customer_a.id
        )
        self.assertEqual(customer_a.id, self.customer_a.id)
        
        # Superuser accessing Client B's customer
        customer_b = get_object_for_user(
            Customers,
            self.superuser,
            id=self.customer_b.id
        )
        self.assertEqual(customer_b.id, self.customer_b.id)
    
    def test_verify_ownership_success(self):
        """Test ownership verification succeeds for valid access."""
        # Should not raise any exception
        verify_object_ownership(self.customer_a, self.user_a)
    
    def test_verify_ownership_cross_tenant_denied(self):
        """Test ownership verification denies cross-tenant access."""
        with self.assertRaises(PermissionDenied):
            verify_object_ownership(self.customer_b, self.user_a)
    
    def test_verify_ownership_superuser_allowed(self):
        """Test superuser can verify ownership across tenants."""
        # Should not raise exception
        verify_object_ownership(self.customer_a, self.superuser)
        verify_object_ownership(self.customer_b, self.superuser)
    
    def test_check_superuser_access(self):
        """Test superuser access check."""
        self.assertFalse(check_superuser_access(self.user_a))
        self.assertFalse(check_superuser_access(self.user_b))
        self.assertTrue(check_superuser_access(self.superuser))


class MultiTenantIsolationTests(TestCase):
    """
    Integration tests for multi-tenant isolation.
    Tests that users cannot access other tenants' data through any means.
    """
    
    def setUp(self):
        """Create test tenants with sample data."""
        # Tenant A
        self.user_a = UserAccount.objects.create(
            username='tenant_a',
            password=make_password('password123'),
            is_client=True
        )
        self.client_a = Clients.objects.create(
            name='Tenant A Inc',
            email='tenanta@example.com',
            user=self.user_a,
            clientId='TA-001'
        )
        
        # Tenant B
        self.user_b = UserAccount.objects.create(
            username='tenant_b',
            password=make_password('password123'),
            is_client=True
        )
        self.client_b = Clients.objects.create(
            name='Tenant B Corp',
            email='tenantb@example.com',
            user=self.user_b,
            clientId='TB-001'
        )
        
        # Create various entities for each tenant
        self.customer_a = Customers.objects.create(
            name='Customer of A',
            customerId='CA-001',
            client=self.client_a
        )
        
        self.customer_b = Customers.objects.create(
            name='Customer of B',
            customerId='CB-001',
            client=self.client_b
        )
        
        self.supplier_a = Suppliers.objects.create(
            name='Supplier of A',
            supplierId='SA-001',
            client=self.client_a
        )
        
        self.supplier_b = Suppliers.objects.create(
            name='Supplier of B',
            supplierId='SB-001',
            client=self.client_b
        )
    
    def test_customer_isolation(self):
        """Test customers are isolated between tenants."""
        # Tenant A can access own customer
        customer = get_object_for_user(Customers, self.user_a, id=self.customer_a.id)
        self.assertEqual(customer.id, self.customer_a.id)
        
        # Tenant A cannot access Tenant B's customer
        with self.assertRaises(Http404):
            get_object_for_user(Customers, self.user_a, id=self.customer_b.id)
    
    def test_supplier_isolation(self):
        """Test suppliers are isolated between tenants."""
        # Tenant B can access own supplier
        supplier = get_object_for_user(Suppliers, self.user_b, id=self.supplier_b.id)
        self.assertEqual(supplier.id, self.supplier_b.id)
        
        # Tenant B cannot access Tenant A's supplier
        with self.assertRaises(Http404):
            get_object_for_user(Suppliers, self.user_b, id=self.supplier_a.id)
    
    def test_same_name_different_tenant(self):
        """
        Test that entities with same name from different tenants remain isolated.
        
        This tests the user's requirement: "even if company A and company B have
        'ABC supplier' it should treat it as separately not same"
        """
        # Create suppliers with identical names in both tenants
        abc_supplier_a = Suppliers.objects.create(
            name='ABC Suppliers Ltd',
            supplierId='ABC-A',
            client=self.client_a
        )
        
        abc_supplier_b = Suppliers.objects.create(
            name='ABC Suppliers Ltd',  # Same name!
            supplierId='ABC-B',
            client=self.client_b
        )
        
        # Tenant A can only access their own ABC Suppliers
        supplier_a = get_object_for_user(
            Suppliers,
            self.user_a,
            id=abc_supplier_a.id
        )
        self.assertEqual(supplier_a.client.id, self.client_a.id)
        
        # Tenant A CANNOT access Tenant B's ABC Suppliers (even though same name)
        with self.assertRaises(Http404):
            get_object_for_user(
                Suppliers,
                self.user_a,
                id=abc_supplier_b.id
            )
        
        # Verify they remain completely separate
        self.assertNotEqual(abc_supplier_a.id, abc_supplier_b.id)
        self.assertEqual(abc_supplier_a.name, abc_supplier_b.name)  # Same name
        self.assertNotEqual(abc_supplier_a.client, abc_supplier_b.client)  # Different clients


class GetClientTests(TestCase):
    """Test the getClient() utility function."""
    
    def setUp(self):
        """Create test users."""
        # Regular client user
        self.client_user = UserAccount.objects.create(
            username='client',
            password=make_password('password'),
            is_client=True
        )
        self.client = Clients.objects.create(
            name='Test Client',
            email='client@example.com',
            user=self.client_user,
            clientId='TC-001'
        )
        
        # Collector user
        self.collector_user = UserAccount.objects.create(
            username='collector',
            password=make_password('password'),
            is_collector=True
        )
        self.collector = Collectors.objects.create(
            name='Test Collector',
            phone='1234567890',
            client=self.client,
            user=self.collector_user
        )
    
    def test_get_client_for_client_user(self):
        """Test getClient returns correct client for client users."""
        client = getClient(self.client_user)
        self.assertEqual(client.id, self.client.id)
    
    def test_get_client_for_collector_user(self):
        """Test getClient returns collector's client."""
        client = getClient(self.collector_user)
        self.assertEqual(client.id, self.client.id)
    
    def test_get_client_for_invalid_user(self):
        """Test getClient returns None for users without client."""
        invalid_user = UserAccount.objects.create(
            username='invalid',
            password=make_password('password')
        )
        client = getClient(invalid_user)
        self.assertIsNone(client)
