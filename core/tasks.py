"""Background tasks for automated campaign execution."""

from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from .models import Campaign, CampaignTarget
from .utils import send_phishing_email


class FakeRequest:
    """Mock request object for background tasks."""
    def __init__(self):
        self.session = {}
        self.POST = {}
        self._messages = FallbackStorage(self)

    def __getitem__(self, key):
        return self.session.get(key)


def send_pending_campaigns_task():
    """
    Background task to check for campaigns that should run and send emails.
    Runs periodically via APScheduler.
    """
    now = timezone.now()
    
    # Find campaigns that should start (draft status, start_date reached, has email template)
    due_campaigns = Campaign.objects.filter(
        status='draft',
        start_date__lte=now,
        email_template__isnull=False
    )
    
    for campaign in due_campaigns:
        try:
            _send_campaign_now(campaign)
        except Exception as e:
            print(f"❌ Error processing campaign '{campaign.name}': {str(e)}")

    # Mark finished campaigns
    finished_campaigns = Campaign.objects.filter(
        status='running',
        end_date__lte=now
    )
    for campaign in finished_campaigns:
        campaign.status = 'finished'
        campaign.save(update_fields=['status'])
        print(f"✓ Campaign '{campaign.name}' marked as finished")


def _send_campaign_now(campaign):
    """Send emails for a campaign and update its status."""
    if not campaign.email_template:
        print(f"⚠️  Campaign '{campaign.name}' has no email template, skipping.")
        return

    if not campaign.sender_account:
        print(f"❌ Campaign '{campaign.name}' has no sender account configured.")
        return

    targets = CampaignTarget.objects.filter(campaign=campaign).select_related('target')
    if not targets.exists():
        print(f"⚠️  Campaign '{campaign.name}' has no targets, skipping.")
        return

    now = timezone.now()
    if now < campaign.end_date:
        campaign.status = 'running'
        campaign.save(update_fields=['status'])
    else:
        campaign.status = 'finished'
        campaign.save(update_fields=['status'])

    sent_count = 0
    fail_count = 0
    
    for ct in targets:
        if ct.sent_at is None:  # Only send to targets that haven't received the email yet
            try:
                send_phishing_email(campaign, ct.target, campaign.email_template)
                ct.sent_at = timezone.now()
                ct.save(update_fields=['sent_at'])
                sent_count += 1
            except Exception as e:
                fail_count += 1
                print(f"❌ Failed to send to {ct.target.email}: {str(e)}")

    status_msg = f"✓ Campaign '{campaign.name}' started: {sent_count} sent, {fail_count} failed"
    print(status_msg)
