"""
WhatsApp Integration Views — Django views and AJAX handlers.

Provides:
  - WhatsApp Scan page (QR code display, status polling, unlink)
  - Balance Accounts page (multi-select accounts, batch send)
  - API proxy endpoints to avoid CORS issues

All views are client-scoped via @client_whatsapp_required decorator.
"""

import json
import logging
from functools import wraps

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from core.models import Customers, Suppliers, Godowns
from core.views import getClient, calculate_customer_balance, calculate_supplier_balance
from whatsapp.whatsapp_service import WhatsAppService, WhatsAppServiceError, format_whatsapp_number
from whatsapp.ledger_helper import get_customer_ledger, get_supplier_ledger

logger = logging.getLogger('whatsapp')


# ============================================================
# DECORATORS
# ============================================================

def whatsapp_enabled_check(view_func):
    """Decorator to check if WhatsApp integration is enabled globally."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'WHATSAPP_ENABLED', True):
            return JsonResponse({'error': 'WhatsApp integration is disabled'}, status=503)
        return view_func(request, *args, **kwargs)
    return wrapper


def client_whatsapp_required(view_func):
    """
    Decorator that:
    1. Checks global WHATSAPP_ENABLED
    2. Gets the logged-in user's Client record
    3. Verifies client.has_whatsapp_access is True
    4. Injects client_id from client.whatsapp_client_id
    
    The decorated view receives 'client_id' and 'client' as kwargs.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'WHATSAPP_ENABLED', True):
            return JsonResponse({'error': 'WhatsApp integration is disabled'}, status=503)
        
        client = getClient(request.user)
        if not client:
            return JsonResponse({'error': 'No client account found'}, status=403)
        
        if not client.has_whatsapp_access:
            return JsonResponse({'error': 'WhatsApp access not enabled for your account'}, status=403)
        
        if not client.whatsapp_client_id:
            # Auto-generate on first access
            client.save()  # triggers the save() override that generates whatsapp_client_id
            if not client.whatsapp_client_id:
                return JsonResponse({'error': 'Failed to generate WhatsApp client ID'}, status=500)
        
        kwargs['client_id'] = client.whatsapp_client_id
        kwargs['client'] = client
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================
# PAGE VIEWS
# ============================================================

class WhatsAppScanView(View):
    """Renders the WhatsApp QR scan / link management page."""

    def get(self, request):
        client = getClient(request.user)
        
        if not client or not client.has_whatsapp_access:
            raise PermissionDenied("WhatsApp access not enabled for your account")
        
        # Ensure client_id exists
        if not client.whatsapp_client_id:
            client.save()
        
        client_id = client.whatsapp_client_id
        service = WhatsAppService(client_id)
        server_available = service.is_available()
        
        context = {
            'server_available': server_available,
            'whatsapp_enabled': getattr(settings, 'WHATSAPP_ENABLED', True),
            'client_id': client_id,
        }
        if server_available:
            try:
                status = service.get_status()
                context['linked'] = status.get('linked', False)
                context['phone'] = status.get('phone')
                
                # Update client status in DB
                if status.get('linked', False) and client.whatsapp_status != 'linked':
                    client.whatsapp_status = 'linked'
                    client.whatsapp_linked_at = timezone.now()
                    client.save(update_fields=['whatsapp_status', 'whatsapp_linked_at'])
            except WhatsAppServiceError:
                context['linked'] = False
        
        return render(request, 'whatsapp/whatsapp_scan.html', context)


class BalanceAccountsView(View):
    """Renders the balance accounts page — select and send balance via WhatsApp."""

    def get(self, request):
        client = getClient(request.user)
        
        if not client or not client.has_whatsapp_access:
            raise PermissionDenied("WhatsApp access not enabled for your account")
        
        if not client.whatsapp_client_id:
            client.save()
        
        # Fetch customers
        customers = Customers.objects.filter(
            client=client, is_active=True
        ).order_by('name')

        customer_list = []
        for c in customers:
            wa_number = format_whatsapp_number(c.country_code, c.wa)
            customer_list.append({
                'id': c.id,
                'name': c.name or 'Unnamed',
                'account_id': c.customerId or '',
                'balance': str(calculate_customer_balance(c, client)),
                'has_wa': bool(wa_number),
                'type': 'customer',
            })

        # Fetch suppliers
        suppliers = Suppliers.objects.filter(
            client=client, is_active=True
        ).order_by('name')

        supplier_list = []
        for s in suppliers:
            wa_number = format_whatsapp_number(s.country_code, s.wa)
            supplier_list.append({
                'id': s.id,
                'name': s.name or 'Unnamed',
                'account_id': s.supplierId or '',
                'balance': str(calculate_supplier_balance(s, client)),
                'has_wa': bool(wa_number),
                'type': 'supplier',
            })

        context = {
            'customers_json': json.dumps(customer_list),
            'suppliers_json': json.dumps(supplier_list),
            'total_customers': len(customer_list),
            'total_suppliers': len(supplier_list),
            'client_id': client.whatsapp_client_id,
        }
        return render(request, 'whatsapp/balance_accounts.html', context)


# ============================================================
# AJAX API ENDPOINTS
# ============================================================

@require_GET
@client_whatsapp_required
def whatsapp_proxy_qr(request, client_id=None, client=None):
    """Proxy QR image from Node.js to avoid CORS. Returns PNG image or JSON status."""
    try:
        service = WhatsAppService(client_id)
        result = service.get_qr_image()

        if result.get('is_image'):
            return HttpResponse(result['content'], content_type=result['content_type'])
        return JsonResponse(result)

    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


@require_GET
@client_whatsapp_required
def whatsapp_status_api(request, client_id=None, client=None):
    """Returns WhatsApp connection status as JSON."""
    try:
        service = WhatsAppService(client_id)
        status = service.get_status()
        
        # Update client status in DB if changed
        linked = status.get('linked', False)
        if linked and client.whatsapp_status != 'linked':
            client.whatsapp_status = 'linked'
            client.whatsapp_linked_at = timezone.now()
            client.save(update_fields=['whatsapp_status', 'whatsapp_linked_at'])
        elif not linked and client.whatsapp_status == 'linked':
            client.whatsapp_status = 'pending'
            client.save(update_fields=['whatsapp_status'])
        
        return JsonResponse(status)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


@require_POST
@client_whatsapp_required
def whatsapp_unlink_api(request, client_id=None, client=None):
    """Unlinks WhatsApp session for this client."""
    try:
        service = WhatsAppService(client_id)
        result = service.unlink()
        
        # Update client status
        client.whatsapp_status = 'inactive'
        client.save(update_fields=['whatsapp_status'])
        
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@client_whatsapp_required
def send_balance_api(request, client_id=None, client=None):
    """
    Collects selected accounts from POST data, prepares payloads,
    and sends to Node.js for batch processing.
    
    For accounts with send_mode='image', fetches actual ledger transactions
    from the database so a trade table image can be generated.
    """
    try:
        data = json.loads(request.body)
        account_ids = data.get('account_ids', [])
        account_type = data.get('account_type', 'all')
        account_modes = data.get('account_modes', {})
        date_from = data.get('date_from', None)
        date_to = data.get('date_to', None)

        if not account_ids:
            return JsonResponse({'error': 'No accounts selected'}, status=400)

        accounts_payload = []

        # Collect customer data
        if account_type in ('customer', 'all'):
            customer_ids = [aid for aid in account_ids if str(aid).startswith('c_')]
            clean_ids = [int(str(aid).replace('c_', '')) for aid in customer_ids]
            customers = Customers.objects.filter(
                id__in=clean_ids, is_active=True, client=client
            )
            for c in customers:
                prefix_id = f'c_{c.id}'
                wa_number = format_whatsapp_number(c.country_code, c.wa)
                mode = account_modes.get(prefix_id, 'text')

                payload = {
                    'name': c.name or 'Unnamed Customer',
                    'whatsappnumber': wa_number or '',
                    'balance': str(calculate_customer_balance(c, client)),
                    'transactions': [],
                    'opening_balance': '0.00',
                    'optin_verified': True,
                    'send_mode': mode,
                }

                # Fetch real transactions for image mode
                if mode == 'image':
                    ledger = get_customer_ledger(c, client, date_from, date_to)
                    payload['transactions'] = ledger['transactions']
                    payload['opening_balance'] = ledger['opening_balance']
                    payload['balance'] = ledger['closing_balance']

                accounts_payload.append(payload)

        # Collect supplier data
        if account_type in ('supplier', 'all'):
            supplier_ids = [aid for aid in account_ids if str(aid).startswith('s_')]
            clean_ids = [int(str(aid).replace('s_', '')) for aid in supplier_ids]
            suppliers = Suppliers.objects.filter(
                id__in=clean_ids, is_active=True, client=client
            )
            for s in suppliers:
                prefix_id = f's_{s.id}'
                wa_number = format_whatsapp_number(s.country_code, s.wa)
                mode = account_modes.get(prefix_id, 'text')

                payload = {
                    'name': s.name or 'Unnamed Supplier',
                    'whatsappnumber': wa_number or '',
                    'balance': str(calculate_supplier_balance(s, client)),
                    'transactions': [],
                    'opening_balance': '0.00',
                    'optin_verified': True,
                    'send_mode': mode,
                }

                if mode == 'image':
                    ledger = get_supplier_ledger(s, client, date_from, date_to)
                    payload['transactions'] = ledger['transactions']
                    payload['opening_balance'] = ledger['opening_balance']
                    payload['balance'] = ledger['closing_balance']

                accounts_payload.append(payload)

        if not accounts_payload:
            return JsonResponse({'error': 'No valid accounts found'}, status=400)

        service = WhatsAppService(client_id)
        result = service.send_balance_accounts(accounts_payload)
        return JsonResponse(result)

    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'send_balance_api error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@client_whatsapp_required
def send_address_rows_api(request, client_id=None, client=None):
    """
    Sends address view rows to a supplier via WhatsApp.
    Each row sent one-by-one as 'description=amount'.
    """
    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        supplier_id = data.get('supplier_id')
        whatsapp_number = data.get('whatsapp_number')
        is_nsd = data.get('is_nsd', True)

        if not rows:
            return JsonResponse({'error': 'No rows to send'}, status=400)

        # Resolve supplier_id to WhatsApp number if not provided directly
        supplier_name = ''
        if not whatsapp_number and supplier_id:
            try:
                if is_nsd:
                    party = Suppliers.objects.get(id=supplier_id, client=client, is_active=True)
                else:
                    party = Godowns.objects.get(id=supplier_id, client=client, is_active=True)
                whatsapp_number = format_whatsapp_number(party.country_code, party.wa)
                supplier_name = party.name or ''
            except Exception:
                return JsonResponse({'error': 'Party not found'}, status=404)

        if not whatsapp_number:
            return JsonResponse({'error': 'Party has no WhatsApp number'}, status=400)

        service = WhatsAppService(client_id)
        result = service.send_address_rows(whatsapp_number, rows, supplier_name)
        return JsonResponse(result)

    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'send_address_rows_api error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
@client_whatsapp_required
def job_status_api(request, job_id, client_id=None, client=None):
    """Proxy job status from Node.js."""
    try:
        service = WhatsAppService(client_id)
        result = service.get_job_status(job_id)
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


@require_POST
@client_whatsapp_required
def cancel_job_api(request, job_id, client_id=None, client=None):
    """Cancel a running batch job."""
    try:
        service = WhatsAppService(client_id)
        result = service.cancel_job(job_id)
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


@require_POST
@client_whatsapp_required
def cancel_all_jobs_api(request, client_id=None, client=None):
    """Cancel ALL running jobs for this client (global stop)."""
    try:
        service = WhatsAppService(client_id)
        result = service.cancel_all_jobs()
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
