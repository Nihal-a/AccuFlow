"""
WhatsApp Service — Django HTTP client for Node.js WhatsApp API.

Handles all communication between Django and the Node.js Express server.
Uses requests library with timeout, retry logic, and error handling.
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger('whatsapp')


class WhatsAppServiceError(Exception):
    """Custom exception for WhatsApp service errors."""
    pass


class WhatsAppService:
    """
    HTTP client for the Node.js WhatsApp Express API.
    
    Usage:
        service = WhatsAppService()
        status = service.get_status()
        service.send_ledger(customer_data)
    """

    def __init__(self):
        self.base_url = getattr(settings, 'WHATSAPP_NODE_URL', 'http://localhost:3001')
        self.api_key = getattr(settings, 'WHATSAPP_API_KEY', 'accuflow-wa-dev-key-2024')
        self.timeout = getattr(settings, 'WHATSAPP_TIMEOUT', 30)
        self.enabled = getattr(settings, 'WHATSAPP_ENABLED', True)

    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key
        }

    def _request(self, method, endpoint, **kwargs):
        """
        Make an HTTP request to the Node.js server.
        Returns parsed JSON response or raises WhatsAppServiceError.
        """
        if not self.enabled:
            raise WhatsAppServiceError('WhatsApp integration is disabled')

        url = f'{self.base_url}{endpoint}'
        kwargs.setdefault('headers', self._headers())
        kwargs.setdefault('timeout', self.timeout)

        try:
            response = requests.request(method, url, **kwargs)

            # For QR image endpoint, return raw response
            if endpoint == '/qr.png' and response.headers.get('Content-Type', '').startswith('image/'):
                return {
                    'is_image': True,
                    'content': response.content,
                    'content_type': response.headers['Content-Type']
                }

            # Parse JSON
            data = response.json()

            if response.status_code == 503:
                raise WhatsAppServiceError('WhatsApp not connected. Please scan QR code first.')
            
            if response.status_code == 403:
                raise WhatsAppServiceError('API authentication failed. Check WHATSAPP_API_KEY.')

            if response.status_code >= 500:
                raise WhatsAppServiceError(f'Node.js server error: {data.get("error", "Unknown")}')

            return data

        except requests.ConnectionError:
            raise WhatsAppServiceError(
                'Cannot connect to WhatsApp server. '
                'Make sure the Node.js server is running on ' + self.base_url
            )
        except requests.Timeout:
            raise WhatsAppServiceError('WhatsApp server request timed out')
        except requests.JSONDecodeError:
            # Could be a non-JSON response (shouldn't happen except for QR image)
            raise WhatsAppServiceError('Invalid response from WhatsApp server')
        except WhatsAppServiceError:
            raise
        except Exception as e:
            logger.error(f'WhatsApp service error: {e}')
            raise WhatsAppServiceError(f'Unexpected error: {str(e)}')

    # --- PRE-FLIGHT CHECK ---

    def ensure_connected(self):
        """
        Pre-flight check: verifies Node.js server is reachable AND WhatsApp is linked.
        Call before every send operation.
        Raises WhatsAppServiceError if not ready.
        """
        try:
            status = self.get_status()
        except WhatsAppServiceError:
            raise WhatsAppServiceError(
                'WhatsApp service unavailable. Make sure the Node.js server is running.'
            )

        if not status.get('linked', False):
            raise WhatsAppServiceError(
                'WhatsApp not linked. Please scan the QR code first at /whatsapp/scan/'
            )

        if not status.get('safe_time', True):
            logger.warning('Sending outside safe hours (8AM-10PM Dubai). Messages may be delayed.')

        return status

    # --- PUBLIC API ---

    def get_status(self):
        """Get WhatsApp connection status."""
        return self._request('GET', '/status')

    def get_qr_image(self):
        """
        Get QR code image. 
        Returns dict with either:
          - {'is_image': True, 'content': bytes, 'content_type': str}
          - {'linked': True, ...} if already linked
          - {'linked': False, 'message': '...'} if QR not yet generated
        """
        return self._request('GET', '/qr.png')

    def unlink(self):
        """Unlink WhatsApp session."""
        return self._request('POST', '/unlink')

    def send_ledger(self, customer_data):
        """
        Send ledger to a single customer/supplier.
        
        Args:
            customer_data: dict with keys:
                - whatsappnumber: str (country_code + number, e.g., '919846080265')
                - balance: str
                - opening_balance: str (optional)
                - transactions: list of dicts (optional)
                - optin_verified: bool (optional)
        """
        self.ensure_connected()
        return self._request('POST', '/api/send-ledger', json={
            'customer_data': customer_data
        })

    def send_balance_accounts(self, accounts):
        """
        Send balance to multiple accounts (batch with Poisson delays).
        
        Args:
            accounts: list of dicts, each with:
                - name: str
                - whatsappnumber: str (country_code + number)
                - balance: str
                - transactions: list (optional)
                - send_mode: 'text' or 'image' (per-account)
        
        Returns:
            dict with 'job_id' for tracking progress
        """
        self.ensure_connected()
        return self._request('POST', '/api/send-balance-accounts', json={
            'accounts': accounts
        })

    def send_address_row(self, whatsapp_number, row_data):
        """
        Send a single address row as text message.
        
        Args:
            whatsapp_number: str (country_code + number)
            row_data: dict with keys: sno, description, amount, qty, date
        """
        self.ensure_connected()
        return self._request('POST', '/api/send-address-row', json={
            'whatsapp_number': whatsapp_number,
            'row_data': row_data
        })

    def send_address_rows(self, whatsapp_number, rows, supplier_name=None):
        """
        Send multiple address rows as batch.
        
        Args:
            whatsapp_number: str (country_code + number)
            rows: list of dicts with keys: sno, description, qty, date
            supplier_name: str (optional, for header message)
        
        Returns:
            dict with 'job_id' for tracking progress
        """
        self.ensure_connected()
        return self._request('POST', '/api/send-address-rows', json={
            'whatsapp_number': whatsapp_number,
            'rows': rows,
            'supplier_name': supplier_name
        })

    def get_job_status(self, job_id):
        """Get batch job status by ID."""
        return self._request('GET', f'/api/job-status/{job_id}')

    def cancel_job(self, job_id):
        """Cancel a running batch job."""
        return self._request('POST', f'/api/cancel-job/{job_id}')

    def is_available(self):
        """Check if WhatsApp server is running and reachable."""
        try:
            status = self.get_status()
            return True
        except WhatsAppServiceError:
            return False

    def is_linked(self):
        """Check if WhatsApp is linked (authenticated)."""
        try:
            status = self.get_status()
            return status.get('linked', False)
        except WhatsAppServiceError:
            return False


def format_whatsapp_number(country_code, wa_number):
    """
    Combine country_code and wa fields from Django model into format
    expected by the Node.js server.
    
    Args:
        country_code: str, e.g., '91'
        wa_number: str, e.g., '9846080265'
    
    Returns:
        str: e.g., '919846080265'
        None: if inputs are invalid
    """
    if not country_code or not wa_number:
        return None
    
    # Clean up
    cc = str(country_code).strip().replace('+', '')
    num = str(wa_number).strip().replace(' ', '').replace('-', '')
    
    if not cc or not num:
        return None
    
    return f'{cc}{num}'
