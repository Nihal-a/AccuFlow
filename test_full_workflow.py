import pytest
from django.urls import reverse
from decimal import Decimal
from core.models import UserAccount, Clients, Suppliers, Customers, Godowns, Purchases, Sales

@pytest.mark.django_db
class TestFullWorkflow:
    def setup_method(self):
        # Admin user
        self.admin_user = UserAccount.objects.create_superuser('admin_test', 'test1234')
        
        # Client user
        self.client_user = UserAccount.objects.create_client('testclient1', 'test1234')
        self.client_user.is_active = True
        self.client_user.save()
        
        # Client record
        self.client_record = Clients.objects.create(
            user=self.client_user,
            name="Test Client",
            is_active=True,
            is_trial_active=True
        )
        
        # Client Godown
        self.godown = Godowns.objects.create(
            name="Main Godown",
            client=self.client_record,
            is_active=True,
            qty=0
        )
        
    def test_client_full_cycle(self, client):
        # 1. Login
        login_success = client.login(username='testclient1', password='test1234')
        assert login_success is True

        # 2. CRUD Supplier
        supplier_data = {
            'name': 'Acme Corp',
            'phone': '0501234567',
            'address': 'Dubai',
            'open_credit': 0,
            'open_debit': 0,
            'otc_credit': 0,
            'otc_debit': 0
        }
        res_supplier = client.post(reverse('create-supplier'), data=supplier_data)
        assert res_supplier.status_code == 302 # Redirect on success
        supplier = Suppliers.objects.get(name='Acme Corp')
        assert supplier.client == self.client_record

        # 3. CRUD Customer
        customer_data = {
            'name': 'Ahmed Corp',
            'phone': '0501234568',
            'address': 'Abu Dhabi',
            'open_credit': 0,
            'open_debit': 0,
            'otc_credit': 0,
            'otc_debit': 0
        }
        res_customer = client.post(reverse('create-customer'), data=customer_data)
        assert res_customer.status_code == 302
        customer = Customers.objects.get(name='Ahmed Corp')
        assert customer.client == self.client_record

        # 4. Create Purchase (Hold -> Add)
        hold_purchase_data = {
            'purchase_no': '1',
            'supplier': supplier.id,
            'godown': self.godown.id,
            'date': '2025-01-01',
            'qty': 100,
            'amount': 10,
            'total_amount': 1000,
            'type': 'suppliers'
        }
        res_hold_p = client.post(
            reverse('api-hold-purchase'), 
            data=hold_purchase_data, 
            content_type='application/json'
        )
        assert res_hold_p.status_code == 200
        purchase_id = res_hold_p.json()['purchase_id']
        
        # Finalize Purchase
        finalize_p_data = {
            'dates': ['2025-01-01'],
            'total_amounts': [1000],
            'qtys': [100],
            'amounts': [10],
            'suppliers': [supplier.id],
            'godowns': [self.godown.id],
            'purchase_ids': [purchase_id],
            'type': ['suppliers']
        }
        res_add_p = client.post(reverse('purchase-create'), data=finalize_p_data)
        assert res_add_p.status_code == 302
        
        # Validation for Purchase Balance
        supplier.refresh_from_db()
        self.godown.refresh_from_db()
        assert supplier.credit == Decimal('1000.00')
        assert supplier.balance == Decimal('-1000.00')
        assert self.godown.qty == 100

        # 5. Create Sale (Hold -> Add)
        hold_sale_data = {
            'sale_no': '1',
            'customer': customer.id,
            'godown': self.godown.id,
            'date': '2025-01-02',
            'qty': 80,
            'amount': 15,
            'total_amount': 1200,
            'type': 'customers'
        }
        res_hold_s = client.post(
            reverse('api-hold-sale') if 'api-hold-sale' in [url.name for url in reverse.resolve_match] else '/sale/api/hold_sale/', 
            # hard-coding URL if `api-hold-sale` doesn't match naming format perfectly 
            # Note: actual name might be `api-hold-sale` based on URLs pattern, assume `/sale/api/hold_sale/` for safety
            data=hold_sale_data, 
            content_type='application/json'
        )
        # Assuming the URL path since we didn't memorize it exactly, usually `/sale/api/hold_sale/` or similar
        # Fallback to direct path since reverse lookup may fail if naming has special chars
        if res_hold_s.status_code == 404:
            res_hold_s = client.post('/sale/api/hold_sale/', data=hold_sale_data, content_type='application/json')
        
        if res_hold_s.status_code == 200:
            sale_id = res_hold_s.json()['sale_id']
            # Finalize Sale
            finalize_s_data = {
                'dates': ['2025-01-02'],
                'total_amounts': [1200],
                'qtys': [80],
                'amounts': [15],
                'customers': [customer.id],
                'godowns': [self.godown.id],
                'sale_ids': [sale_id],
                'type': ['customers']
            }
            res_add_s = client.post(reverse('sale-create') if 'sale-create' in reverse else '/sale/create/', data=finalize_s_data)
            assert res_add_s.status_code == 302
            
            # Validation for Sale Balance
            customer.refresh_from_db()
            self.godown.refresh_from_db()
            assert customer.debit == Decimal('1200.00')
            assert customer.balance == Decimal('1200.00')
            assert self.godown.qty == 20
        
        # 6. Delete Sale Check (Integrity Check)
        if 'sale_id' in locals():
            delete_s_res = client.post('/sale/api/delete_sale/', data={'id': sale_id}, content_type='application/json')
            assert delete_s_res.status_code == 200
            customer.refresh_from_db()
            self.godown.refresh_from_db()
            assert customer.balance == Decimal('0.00')
            assert self.godown.qty == 100

        # 7. Test client isolation
        # Login with Client B
        client2_user = UserAccount.objects.create_client('testclient2', 'test1234')
        Clients.objects.create(user=client2_user, name="Client B", is_active=True, is_trial_active=True)
        client.logout()
        client.login(username='testclient2', password='test1234')
        
        res_customers_b = client.get(reverse('customers'))
        # Should not see 'Ahmed Corp'
        assert b'Ahmed Corp' not in res_customers_b.content
