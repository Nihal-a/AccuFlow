"""
WhatsApp Service — Django HTTP client for Node.js WhatsApp API.

Handles all communication between Django and the Node.js Express server.
Uses requests library with timeout, retry logic, and error handling.
Multi-client: each WhatsAppService instance is scoped to a client_id.
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
        service = WhatsAppService(client_id='wa_abc123def456')
        status = service.get_status()
        service.send_ledger(customer_data)
    """
    
    def __init__(self, client_id):
        """
        Initialize with client-specific session.
        
        Args:
            client_id: str — the whatsapp_client_id from the Clients model
        """
        if not client_id:
            raise WhatsAppServiceError("client_id is required for WhatsApp service")
        self.client_id = client_id
        self.base_url = getattr(settings, 'WHATSAPP_NODE_URL', 'http://localhost:3005')
        self.api_key = getattr(settings, 'WHATSAPP_API_KEY', None)
        if not self.api_key:
            raise WhatsAppServiceError("WHATSAPP_API_KEY must be set in Django settings")
        self.timeout = getattr(settings, 'WHATSAPP_TIMEOUT', 30)

    def _headers(self):
        return {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
        }

    def _request(self, method, endpoint, **kwargs):
        """
        Make an HTTP request to the Node.js server.
        All endpoints are scoped under /api/{client_id}/...
        """
        url = f'{self.base_url}/api/{self.client_id}{endpoint}'
        kwargs.setdefault('headers', self._headers())
        kwargs.setdefault('timeout', self.timeout)

        try:
            response = requests.request(method, url, **kwargs)

            # Handle image responses (QR code)
            if response.headers.get('Content-Type', '').startswith('image/'):
                return {
                    'is_image': True,
                    'content': response.content,
                    'content_type': response.headers['Content-Type']
                }

            data = response.json()

            if response.status_code == 403:
                raise WhatsAppServiceError('API key invalid or missing')
            
            if response.status_code == 503:
                raise WhatsAppServiceError(data.get('error', 'WhatsApp service unavailable'))

            if response.status_code >= 400:
                raise WhatsAppServiceError(data.get('error', f'HTTP {response.status_code}'))

            return data

        except requests.exceptions.ConnectionError:
            raise WhatsAppServiceError(
                'Cannot connect to WhatsApp server. '
                'Ensure the Node.js server is running (npm start in wn/ directory).'
            )
        except requests.exceptions.Timeout:
            raise WhatsAppServiceError(
                f'WhatsApp server request timed out after {self.timeout}s'
            )
        except requests.exceptions.JSONDecodeError:
            raise WhatsAppServiceError('Invalid response from WhatsApp server')
        except WhatsAppServiceError:
            raise
        except Exception as e:
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
                'WhatsApp server is not reachable. '
                'Please ensure the Node.js server is running.'
            )
        
        if not status.get('linked', False):
            raise WhatsAppServiceError(
                'WhatsApp is not linked. '
                'Please scan the QR code on the WhatsApp Scan page first.'
            )
        
        if not status.get('safe_time', True):
            logger.warning(f'[{self.client_id}] Sending outside safe hours (Dubai timezone)')
        
        return status

    # --- ENDPOINTS ---

    def get_status(self):
        """Get WhatsApp connection status for this client."""
        return self._request('GET', '/status')

    def get_qr_image(self):
        """
        Get QR code image for this client.
        Returns dict with either:
          - {'is_image': True, 'content': bytes, 'content_type': str}
          - {'linked': True, ...} if already linked
          - {'linked': False, 'message': '...'} if QR not yet generated
        """
        return self._request('GET', '/qr.png')

    def unlink(self):
        """Unlink this client's WhatsApp session."""
        return self._request('POST', '/unlink')

    def send_ledger(self, customer_data):
        """
        Send ledger to a single customer/supplier.
        
        Args:
            customer_data: dict with keys:
                - whatsappnumber: str (country_code + number)
                - balance: str
                - transactions: list of dicts (optional)
        """
        self.ensure_connected()
        return self._request('POST', '/send-ledger', json={
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
        return self._request('POST', '/send-balance-accounts', json={
            'accounts': accounts
        })

    def send_address_row(self, whatsapp_number, row_data):
        """
        Send a single address row as text message.
        """
        self.ensure_connected()
        return self._request('POST', '/send-address-row', json={
            'whatsapp_number': whatsapp_number,
            'row_data': row_data
        })

    def send_address_rows(self, whatsapp_number, rows, supplier_name=None):
        """
        Send multiple address rows as batch.
        
        Returns:
            dict with 'job_id' for tracking progress
        """
        self.ensure_connected()
        return self._request('POST', '/send-address-rows', json={
            'whatsapp_number': whatsapp_number,
            'rows': rows,
            'supplier_name': supplier_name
        })

    def get_job_status(self, job_id):
        """Get batch job status by ID."""
        return self._request('GET', f'/job-status/{job_id}')

    def cancel_job(self, job_id):
        """Cancel a running batch job."""
        return self._request('POST', f'/cancel-job/{job_id}')

    def cancel_all_jobs(self):
        """Cancel ALL running jobs for this client (global stop)."""
        return self._request('POST', '/cancel-all-jobs')

    def is_available(self):
        """Check if WhatsApp server is running and reachable."""
        try:
            # Health endpoint has no client_id scope
            url = f'{self.base_url}/health'
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def is_linked(self):
        """Check if this client's WhatsApp is linked."""
        try:
            status = self.get_status()
            return status.get('linked', False)
        except Exception:
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
    if not wa_number:
        return None
    
    # Clean inputs
    code = str(country_code or '').strip().replace('+', '')
    number = str(wa_number).strip()
    
    # Remove any non-numeric characters
    code = ''.join(filter(str.isdigit, code))
    number = ''.join(filter(str.isdigit, number))
    
    if not number:
        return None
    
    # If number already starts with the country code, don't double-add
    if code and number.startswith(code) and len(number) > len(code) + 5:
        return number
    
    return f'{code}{number}' if code else number
