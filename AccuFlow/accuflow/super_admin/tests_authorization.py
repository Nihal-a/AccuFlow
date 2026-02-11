"""Tests for super_admin module authorization fixes."""

from django.test import TestCase, Client as HttpClient
from django.contrib.auth.hashers import make_password

from core.models import Clients, UserAccount, SubscriptionPlan


class SuperAdminAuthorizationTests(TestCase):
    """Test that super_admin module requires superuser access."""
    
    def setUp(self):
        """Create test users and data."""
        # Regular client user
        self.user_client = UserAccount.objects.create(
            username='regular_user',
            password=make_password('password123'),
            is_client=True,
            is_superuser=False
        )
        self.client_obj = Clients.objects.create(
            name='Regular Company',
            email='regular@example.com',
            user=self.user_client,
            clientId='REG-001'
        )
        
        # Another client
        self.user_client_b = UserAccount.objects.create(
            username='client_b',
            password=make_password('password123'),
            is_client=True,
            is_superuser=False
        )
        self.client_b = Clients.objects.create(
            name='Company B',
            email='b@example.com',
            user=self.user_client_b,
            clientId='B-001'
        )
        
        # Superuser
        self.superuser = UserAccount.objects.create(
            username='admin',
            password=make_password('admin123'),
            is_superuser=True,
            is_client=True
        )
        self.admin_client = Clients.objects.create(
            name='Admin',
            email='admin@example.com',
            user=self.superuser,
            clientId='ADMIN-001'
        )
        
        # Create subscription plan
        self.subscription_plan = SubscriptionPlan.objects.create(
            name='Monthly Plan',
            price=99.99,
            duration_days=30,
            is_trial=False,
            is_active=True
        )
        
        self.http_client = HttpClient()
    
    def test_regular_user_cannot_view_client_update_form(self):
        """Regular users CANNOT access client update forms."""
        self.http_client.force_login(self.user_client)
        
        # Try to view update form for Company B
        response = self.http_client.get(f'/super-admin/clients/update/{self.client_b.id}/')
        
        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403)
    
    def test_regular_user_cannot_update_client(self):
        """Regular users CANNOT update any client."""
        self.http_client.force_login(self.user_client)
        
        # Try to update Company B
        response = self.http_client.post(
            f'/super-admin/clients/update/{self.client_b.id}/',
            {
                'name': 'Hacked Company B',
                'email': 'hacked@example.com',
                'phone': '0000000000',
                'username': 'hacked_user'
            }
        )
        
        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403)
        
        # Verify Company B unchanged
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.name, 'Company B')
    
    def test_regular_user_cannot_delete_client(self):
        """Regular users CANNOT delete clients."""
        self.http_client.force_login(self.user_client)
        
        # Try to delete Company B
        response = self.http_client.get(f'/super-admin/clients/delete/{self.client_b.id}/')
        
        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403)
        
        # Verify Company B still active
        self.client_b.refresh_from_db()
        self.assertTrue(self.client_b.is_active)
    
    def test_regular_user_cannot_view_subscription_update(self):
        """Regular users CANNOT access subscription plan updates."""
        self.http_client.force_login(self.user_client)
        
        response = self.http_client.get(f'/super-admin/subscriptions/update/{self.subscription_plan.id}/')
        
        self.assertEqual(response.status_code, 403)
    
    def test_regular_user_cannot_update_subscription(self):
        """Regular users CANNOT modify subscription plans."""
        self.http_client.force_login(self.user_client)
        
        response = self.http_client.post(
            f'/super-admin/subscriptions/update/{self.subscription_plan.id}/',
            {
                'name': 'FREE Plan',
                'price': 0.00,
                'duration': 365,
                'is_trial': 'on',
                'description': 'Hacked to free',
                'is_active': 'on'
            }
        )
        
        self.assertEqual(response.status_code, 403)
        
        # Verify plan unchanged
        self.subscription_plan.refresh_from_db()
        self.assertEqual(self.subscription_plan.name, 'Monthly Plan')
        self.assertEqual(float(self.subscription_plan.price), 99.99)
    
    def test_superuser_can_view_client_update_form(self):
        """Superusers CAN access client update forms."""
        self.http_client.force_login(self.superuser)
        
        response = self.http_client.get(f'/super-admin/clients/update/{self.client_b.id}/')
        
        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Company B')
    
    def test_superuser_can_update_client(self):
        """Superusers CAN update any client."""
        self.http_client.force_login(self.superuser)
        
        response = self.http_client.post(
            f'/super-admin/clients/update/{self.client_b.id}/',
            {
                'name': 'Updated Company B',
                'email': 'updated@example.com',
                'phone': '1234567890',
                'username': 'client_b'
            }
        )
        
        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)
        
        # Verify update applied
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.name, 'Updated Company B')
    
    def test_superuser_can_delete_client(self):
        """Superusers CAN delete clients."""
        self.http_client.force_login(self.superuser)
        
        response = self.http_client.get(f'/super-admin/clients/delete/{self.client_b.id}/')
        
        self.assertEqual(response.status_code, 302)
        
        # Verify soft delete
        self.client_b.refresh_from_db()
        self.assertFalse(self.client_b.is_active)
    
    def test_superuser_can_update_subscription(self):
        """Superusers CAN modify subscription plans."""
        self.http_client.force_login(self.superuser)
        
        response = self.http_client.post(
            f'/super-admin/subscriptions/update/{self.subscription_plan.id}/',
            {
                'name': 'Annual Plan',
                'price': 999.99,
                'duration': 365,
                'is_trial': '',
                'description': 'Updated description',
                'is_active': 'on'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Verify update
        self.subscription_plan.refresh_from_db()
        self.assertEqual(self.subscription_plan.name, 'Annual Plan')
        self.assertEqual(float(self.subscription_plan.price), 999.99)
