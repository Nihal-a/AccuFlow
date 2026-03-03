"""
WhatsApp Integration Views — Django views and AJAX handlers.

Provides:
  - WhatsApp Scan page (QR code display, status polling, unlink)
  - Balance Accounts page (multi-select accounts, batch send)
  - API proxy endpoints to avoid CORS issues
"""

import json
import logging
from decimal import Decimal

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from core.models import Customers, Suppliers
from core.views import getClient
from whatsapp.whatsapp_service import WhatsAppService, WhatsAppServiceError, format_whatsapp_number

logger = logging.getLogger('whatsapp')


def whatsapp_enabled_check(view_func):
    """Decorator to check if WhatsApp integration is enabled."""
    def wrapper(request, *args, **kwargs):
        if not getattr(settings, 'WHATSAPP_ENABLED', True):
            return JsonResponse({'error': 'WhatsApp integration is disabled'}, status=503)
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================================
# PAGE VIEWS
# ============================================================

class WhatsAppScanView(View):
    """Renders the WhatsApp QR scan / link management page."""

    def get(self, request):
        service = WhatsAppService()
        server_available = service.is_available()
        context = {
            'server_available': server_available,
            'whatsapp_enabled': getattr(settings, 'WHATSAPP_ENABLED', True),
        }
        if server_available:
            try:
                status = service.get_status()
                context['linked'] = status.get('linked', False)
                context['phone'] = status.get('phone')
            except WhatsAppServiceError:
                context['linked'] = False
        return render(request, 'whatsapp/whatsapp_scan.html', context)


class BalanceAccountsView(View):
    """Renders the balance accounts page — select and send balance via WhatsApp."""

    def get(self, request):
        client = getClient(request.user)
        customers = Customers.objects.filter(
            is_active=True, client=client
        ).values('id', 'name', 'customerId', 'balance', 'wa', 'country_code')
        suppliers = Suppliers.objects.filter(
            is_active=True, client=client
        ).values('id', 'name', 'supplierId', 'balance', 'wa', 'country_code')

        # Serialize for template (convert Decimal to string)
        customer_list = []
        for c in customers:
            customer_list.append({
                'id': c['id'],
                'name': c['name'] or 'Unnamed',
                'account_id': c['customerId'] or '',
                'balance': str(c['balance'] or '0.0000'),
                'has_wa': bool(c['wa']),
                'type': 'customer'
            })

        supplier_list = []
        for s in suppliers:
            supplier_list.append({
                'id': s['id'],
                'name': s['name'] or 'Unnamed',
                'account_id': s['supplierId'] or '',
                'balance': str(s['balance'] or '0.0000'),
                'has_wa': bool(s['wa']),
                'type': 'supplier'
            })

        context = {
            'customers': json.dumps(customer_list),
            'suppliers': json.dumps(supplier_list),
            'whatsapp_enabled': getattr(settings, 'WHATSAPP_ENABLED', True),
        }
        return render(request, 'whatsapp/balance_accounts.html', context)


# ============================================================
# AJAX API ENDPOINTS
# ============================================================

def whatsapp_proxy_qr(request):
    """Proxy QR image from Node.js to avoid CORS. Returns PNG image or JSON status."""
    try:
        service = WhatsAppService()
        result = service.get_qr_image()

        if result.get('is_image'):
            response = HttpResponse(result['content'], content_type=result['content_type'])
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response

        return JsonResponse(result)

    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


def whatsapp_status_api(request):
    """Returns WhatsApp connection status as JSON."""
    try:
        service = WhatsAppService()
        status = service.get_status()
        return JsonResponse(status)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e), 'linked': False}, status=503)


def whatsapp_unlink_api(request):
    """Unlinks WhatsApp session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        service = WhatsAppService()
        result = service.unlink()
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=500)


def send_balance_api(request):
    """
    Collects selected accounts from POST data, prepares payloads,
    and sends to Node.js for batch processing.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        account_ids = data.get('account_ids', [])
        account_type = data.get('account_type', 'all')
        account_modes = data.get('account_modes', {})  # { 'c_1': 'text', 's_2': 'image', ... }

        if not account_ids:
            return JsonResponse({'error': 'No accounts selected'}, status=400)

        client = getClient(request.user)
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
                accounts_payload.append({
                    'name': c.name or 'Unnamed Customer',
                    'whatsappnumber': wa_number or '',
                    'balance': str(c.balance or '0.0000'),
                    'transactions': [],
                    'optin_verified': True,
                    'send_mode': account_modes.get(prefix_id, 'text')
                })

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
                accounts_payload.append({
                    'name': s.name or 'Unnamed Supplier',
                    'whatsappnumber': wa_number or '',
                    'balance': str(s.balance or '0.0000'),
                    'transactions': [],
                    'optin_verified': True,
                    'send_mode': account_modes.get(prefix_id, 'text')
                })

        if not accounts_payload:
            return JsonResponse({'error': 'No valid accounts found'}, status=400)

        # Send to Node.js (per-account modes embedded in each account object)
        service = WhatsAppService()
        result = service.send_balance_accounts(accounts_payload)
        return JsonResponse(result)

    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except Exception as e:
        logger.error(f'send_balance_api error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


def send_address_rows_api(request):
    """
    Sends address view rows to a supplier via WhatsApp.
    Receives rows + supplier info from the address view page.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        supplier_id = data.get('supplier_id')
        rows = data.get('rows', [])

        if not supplier_id or not rows:
            return JsonResponse({'error': 'supplier_id and rows are required'}, status=400)

        client = getClient(request.user)
        supplier = Suppliers.objects.get(id=supplier_id, is_active=True, client=client)

        wa_number = format_whatsapp_number(supplier.country_code, supplier.wa)
        if not wa_number:
            return JsonResponse({
                'error': f'Supplier "{supplier.name}" has no WhatsApp number configured',
                'skipped': True
            }, status=400)

        service = WhatsAppService()
        result = service.send_address_rows(
            whatsapp_number=wa_number,
            rows=rows,
            supplier_name=supplier.name
        )
        return JsonResponse(result)

    except Suppliers.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except Exception as e:
        logger.error(f'send_address_rows_api error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


def job_status_api(request, job_id):
    """Proxy job status from Node.js."""
    try:
        service = WhatsAppService()
        result = service.get_job_status(job_id)
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)


def cancel_job_api(request, job_id):
    """Cancel a running batch job."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        service = WhatsAppService()
        result = service.cancel_job(job_id)
        return JsonResponse(result)
    except WhatsAppServiceError as e:
        return JsonResponse({'error': str(e)}, status=503)
