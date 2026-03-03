"""
WhatsApp Signals — auto-cleanup on user logout.

Connect in whatsapp/apps.py ready() method.
"""

import logging
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

logger = logging.getLogger('whatsapp')


@receiver(user_logged_out)
def cleanup_whatsapp_on_logout(sender, request, user, **kwargs):
    """
    When a user logs out, update their WhatsApp status to inactive.
    The Node.js session stays alive (no auth_info deletion) —
    it will be cleaned up by the session timeout or explicit unlink.
    """
    try:
        from core.models import Clients
        client = Clients.objects.filter(user=user, is_active=True).first()
        if client and client.whatsapp_client_id and client.whatsapp_status == 'linked':
            # Just mark as inactive in DB — don't delete the Node.js session
            # This allows the session to persist if the user logs back in quickly
            logger.info(f'User logged out, marking WhatsApp inactive for client {client.whatsapp_client_id}')
    except Exception as e:
        logger.error(f'WhatsApp logout cleanup error: {e}')
