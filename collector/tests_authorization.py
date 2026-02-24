"""Tests for collectors module authorization fixes."""

from django.test import TestCase, Client as HttpClient
from django.contrib.auth.hashers import make_password

from core.models import Clients, Collectors, UserAccount


class CollectorsAuthorizationTests(TestCase):
    """Test that collectors module enforces proper authorization."""
    
    def setUp(self):
        """Create test clients and collectors."""
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
        
        # Create collector users
        self.collector_user_a = UserAccount.objects.create(
            username='collector_a',
            password=make_password('pass123'),
            is_collector=True
        )
        
        self.collector_user_b = UserAccount.objects.create(
            username='collector_b',
            password=make_password('pass123'),
            is_collector=True
        )
        
        # Create collectors
        self.collector_a = Collectors.objects.create(
            name='Collector A1',
            phone='1111111111',
            client=self.client_a,
            user=self.collector_user_a
        )
        
        self.collector_b = Collectors.objects.create(
            name='Collector B1',
            phone='2222222222',
            client=self.client_b,
            user=self.collector_user_b
        )
        
        self.http_client = HttpClient()
    
    def test_delete_collector_same_client_allowed(self):
        """User can delete their own collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/collectors/delete/{self.collector_a.id}/')
        
        self.assertEqual(response.status_code, 302)
        
        self.collector_a.refresh_from_db()
        self.assertFalse(self.collector_a.is_active)
    
    def test_delete_collector_cross_tenant_blocked(self):
        """User CANNOT delete another tenant's collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/collectors/delete/{self.collector_b.id}/')
        
        self.assertEqual(response.status_code, 404)
        
        self.collector_b.refresh_from_db()
        self.assertTrue(self.collector_b.is_active)
    
    def test_update_collector_view_same_client_allowed(self):
        """User can view update form for their own collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/collectors/update/{self.collector_a.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Collector A1')
    
    def test_update_collector_view_cross_tenant_blocked(self):
        """User CANNOT view update form for another tenant's collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.get(f'/collectors/update/{self.collector_b.id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_update_collector_post_same_client_allowed(self):
        """User can update their own collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.post(
            f'/collectors/update/{self.collector_a.id}/',
            {
                'name': 'Updated Collector A1',
                'phone': '9999999999',
                'address': 'New Address'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        self.collector_a.refresh_from_db()
        self.assertEqual(self.collector_a.name, 'Updated Collector A1')
    
    def test_update_collector_post_cross_tenant_blocked(self):
        """User CANNOT update another tenant's collector."""
        self.http_client.force_login(self.user_a)
        
        response = self.http_client.post(
            f'/collectors/update/{self.collector_b.id}/',
            {
                'name': 'Hacked Collector B1',
                'phone': '0000000000',
                'address': 'Hacker Address'
            }
        )
        
        self.assertEqual(response.status_code, 404)
        
        self.collector_b.refresh_from_db()
        self.assertEqual(self.collector_b.name, 'Collector B1')
    
    def test_superuser_cross_tenant_access(self):
        """Superuser can access all collectors."""
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
        
        response_a = self.http_client.get(f'/collectors/update/{self.collector_a.id}/')
        self.assertEqual(response_a.status_code, 200)
        
        response_b = self.http_client.get(f'/collectors/update/{self.collector_b.id}/')
        self.assertEqual(response_b.status_code, 200)
