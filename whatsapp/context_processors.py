"""
WhatsApp context processor — injects WhatsApp access flag into all templates.

Add to settings.py TEMPLATES context_processors:
    'whatsapp.context_processors.whatsapp_context'
"""

from core.views import getClient


def whatsapp_context(request):
    """Inject client_has_whatsapp flag for sidebar visibility."""
    if not request.user.is_authenticated:
        return {'client_has_whatsapp': False}
    
    client = getClient(request.user)
    if not client:
        return {'client_has_whatsapp': False}
    
    return {
        'client_has_whatsapp': bool(client.has_whatsapp_access),
    }
