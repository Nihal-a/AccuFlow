"""
Management command to clean up inactive WhatsApp sessions.

Usage:
    python manage.py cleanup_whatsapp_sessions
    python manage.py cleanup_whatsapp_sessions --days 30

Schedule weekly via cron:
    0 3 * * 0 cd /path/to/project && python manage.py cleanup_whatsapp_sessions
"""

import logging
import requests
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from core.models import Clients

logger = logging.getLogger('whatsapp')


class Command(BaseCommand):
    help = 'Clean up inactive WhatsApp sessions older than N days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=30,
            help='Delete sessions inactive for more than N days (default: 30)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be cleaned without making changes'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        self.stdout.write(f'Looking for sessions inactive for >{days} days (before {cutoff})...')

        # Find clients with stale WhatsApp links
        stale_clients = Clients.objects.filter(
            has_whatsapp_access=True,
            whatsapp_status='linked',
            whatsapp_linked_at__lt=cutoff
        )

        if not stale_clients.exists():
            self.stdout.write(self.style.SUCCESS('No stale sessions found.'))
            return

        node_url = getattr(settings, 'WHATSAPP_NODE_URL', 'http://localhost:3001')
        api_key = getattr(settings, 'WHATSAPP_API_KEY', 'accuflow-wa-dev-key-2024')

        for client in stale_clients:
            client_id = client.whatsapp_client_id
            if not client_id:
                continue

            self.stdout.write(f'  [{client_id}] {client.name} — last linked: {client.whatsapp_linked_at}')

            if dry_run:
                self.stdout.write(self.style.WARNING(f'    [DRY RUN] Would unlink'))
                continue

            try:
                # Unlink on Node.js
                response = requests.post(
                    f'{node_url}/api/{client_id}/unlink',
                    headers={'X-API-Key': api_key},
                    timeout=10
                )
                if response.status_code == 200:
                    self.stdout.write(self.style.SUCCESS(f'    ✅ Unlinked on Node.js'))
                else:
                    self.stdout.write(self.style.WARNING(f'    ⚠️ Node.js returned {response.status_code}'))
            except requests.exceptions.ConnectionError:
                self.stdout.write(self.style.WARNING(f'    ⚠️ Node.js not reachable — skipping server cleanup'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ❌ Error: {e}'))

            # Update DB
            client.whatsapp_status = 'inactive'
            client.save(update_fields=['whatsapp_status'])
            self.stdout.write(self.style.SUCCESS(f'    ✅ Marked inactive in DB'))

        total = stale_clients.count()
        self.stdout.write(self.style.SUCCESS(f'\nDone. Processed {total} stale session(s).'))
