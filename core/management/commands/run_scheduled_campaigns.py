from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Campaign
from core.utils import send_phishing_email

class Command(BaseCommand):
    help = 'Send all campaign emails when their start_date has passed'

    def handle(self, *args, **options):
        now = timezone.now()
        due_campaigns = Campaign.objects.filter(start_date__lte=now, status='draft', email_template__isnull=False)

        if not due_campaigns.exists():
            self.stdout.write(self.style.SUCCESS('No scheduled campaigns are due.'))
            return

        for campaign in due_campaigns:
            targets = campaign.campaigntarget_set.select_related('target').all()
            if not targets:
                self.stdout.write(self.style.WARNING(f"Campaign '{campaign.name}' has no targets and was skipped."))
                continue

            sent_count = 0
            fail_count = 0
            for ct in targets:
                try:
                    send_phishing_email(campaign, ct.target, campaign.email_template)
                    ct.sent_at = timezone.now()
                    ct.save()
                    sent_count += 1
                except Exception as e:
                    fail_count += 1
                    self.stdout.write(self.style.ERROR(f"Failed to send to {ct.target.email}: {str(e)}"))

            campaign.status = 'finished'
            campaign.save(update_fields=['status'])
            self.stdout.write(self.style.SUCCESS(
                f"Campaign '{campaign.name}' started automatically: {sent_count} emails sent, {fail_count} failed."
            ))
