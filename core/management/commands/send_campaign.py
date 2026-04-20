from django.core.management.base import BaseCommand
from django.utils import timezone  # <-- add this import
from core.models import Campaign, EmailTemplate
from core.utils import send_phishing_email

class Command(BaseCommand):
    help = 'Send phishing emails for a given campaign'

    def add_arguments(self, parser):
        parser.add_argument('campaign_id', type=int)

    def handle(self, *args, **options):
        campaign_id = options['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)
        
        # Get all targets associated with this campaign
        targets = campaign.campaigntarget_set.select_related('target').all()
        
        email_template = campaign.email_template or EmailTemplate.objects.first()
        if not email_template:
            self.stdout.write(self.style.ERROR('No email template found. Set one on the campaign or create one in admin.'))
            return
        
        for ct in targets:
            target = ct.target
            self.stdout.write(f"Sending to {target.email}...")
            send_phishing_email(campaign, target, email_template)
            ct.sent_at = timezone.now()
            ct.save()
        
        self.stdout.write(self.style.SUCCESS(f"Campaign '{campaign.name}' sent successfully!"))