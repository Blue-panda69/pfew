"""
Django management command to send pending campaigns.
Can be run manually or scheduled via cron/APScheduler.

Usage:
    python manage.py send_pending_campaigns
    python manage.py send_pending_campaigns --daemon (runs in a loop every 10 seconds)
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import time
import sys


class Command(BaseCommand):
    help = 'Send pending campaigns based on their start_date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run continuously as a daemon, checking every 10 seconds',
        )

    def handle(self, *args, **options):
        if options['daemon']:
            self.run_daemon()
        else:
            self.send_pending_campaigns()

    def send_pending_campaigns(self):
        """Send campaigns that are due."""
        from core.tasks import send_pending_campaigns_task
        self.stdout.write("🔄 Checking for pending campaigns...")
        try:
            send_pending_campaigns_task()
            self.stdout.write(self.style.SUCCESS("✓ Campaign check completed"))
        except Exception as e:
            raise CommandError(f"Error sending campaigns: {e}")

    def run_daemon(self):
        """Run as a daemon, continuously checking for campaigns."""
        self.stdout.write(self.style.SUCCESS("🚀 Starting campaign daemon (checking every 10 seconds)..."))
        self.stdout.write("Press Ctrl+C to stop\n")
        
        try:
            while True:
                try:
                    from core.tasks import send_pending_campaigns_task
                    send_pending_campaigns_task()
                except Exception as e:
                    self.stderr.write(f"❌ Error: {e}")
                
                time.sleep(10)
        except KeyboardInterrupt:
            self.stdout.write("\n✓ Campaign daemon stopped")
            sys.exit(0)
