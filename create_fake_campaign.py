import os
import django
from datetime import timedelta
from django.utils import timezone

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()

    from core.models import Campaign, EmailTemplate, LandingPage, Target, CampaignTarget, TrackingEvent, SmtpAccount

    now = timezone.now()
    start = now - timedelta(hours=24)

    sender, _ = SmtpAccount.objects.get_or_create(
        email='phish-sender@example.com',
        defaults={'password': 'app-password', 'is_active': True},
    )

    landing, _ = LandingPage.objects.get_or_create(
        slug='fake-24h-funnel',
        defaults={
            'title': 'Security Verification Required',
            'content': (
                '<div style="padding:20px;font-family:Arial, sans-serif;max-width:600px;margin:0 auto;background:#fff;' 
                'border-radius:12px;border:1px solid #ddd;">'
                '<h1>Security verification required</h1>'
                '<p>To keep your account secure, please review the verification details below.</p>'
                '<form>'
                '<label>Email</label>'
                '<input type="text" value="{{ email }}" disabled style="width:100%;padding:10px;margin:8px 0;' 
                'border:1px solid #ccc;border-radius:6px;">'
                '<label>Password</label>'
                '<input type="password" placeholder="Enter current password" style="width:100%;padding:10px;margin:8px 0;' 
                'border:1px solid #ccc;border-radius:6px;">'
                '<button type="submit" style="display:inline-block;padding:12px 20px;background:#1d4ed8;color:#fff;' 
                'border:none;border-radius:8px;">Verify account</button>'
                '</form>'
                '</div>'
            ),
            'css_content': (
                'body { background:#f4f7fb; margin:0; font-family:Arial,sans-serif; } '
                '.landing-page-wrapper { max-width:640px; margin:40px auto; padding:24px; background:#fff; ' 
                'border-radius:16px; box-shadow:0 16px 35px rgba(15,23,42,.08); } input { box-sizing:border-box; } '
            ),
        },
    )

    template, _ = EmailTemplate.objects.get_or_create(
        name='Fake Security Alert Template',
        defaults={
            'subject': 'Important security verification required',
            'html_content': (
                '<html><body><p>Dear {{ first_name }} {{ last_name }},</p>'
                '<p>Please verify your account immediately.</p>'
                '<p><a href="{{ tracking_link }}">Verify Account</a></p>'
                '</body></html>'
            ),
            'plain_text_content': (
                'Dear {{ first_name }} {{ last_name }},\n'
                'Please verify your account immediately.\n'
                '{{ tracking_link }}'
            ),
        },
    )

    campaign_name = 'Fake 24h Funnel Campaign'
    Campaign.objects.filter(name=campaign_name).delete()

    campaign = Campaign.objects.create(
        name=campaign_name,
        sender_account=sender,
        description='Fake finished campaign for UI preview',
        email_template=template,
        landing_page=landing,
        start_date=start,
        end_date=now,
        status='finished',
    )

    total = 50
    for i in range(1, total + 1):
        email = f'user{i:02d}@example.com'
        first = f'User{i:02d}'
        target, _ = Target.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first,
                'last_name': 'Test',
                'department': 'Sales' if i % 3 == 0 else 'Engineering' if i % 3 == 1 else 'HR',
                'groups': 'Test Group',
            },
        )
        sent_at = start + timedelta(minutes=i * 20)
        CampaignTarget.objects.update_or_create(
            campaign=campaign,
            target=target,
            defaults={'sent_at': sent_at},
        )

        def create_event(event_type, when):
            TrackingEvent.objects.create(
                campaign=campaign,
                target=target,
                event_type=event_type,
                timestamp=when,
                ip_address=f'192.168.1.{(target.id % 254) + 1}',
                user_agent='Mozilla/5.0',
            )

        idx = i - 1
        if idx < 10:
            continue
        elif idx < 25:
            create_event('open', start + timedelta(hours=1 + idx * 0.5))
        elif idx < 40:
            create_event('open', start + timedelta(hours=1 + idx * 0.4))
            create_event('click', start + timedelta(hours=2 + idx * 0.4))
        else:
            create_event('open', start + timedelta(hours=1 + idx * 0.3))
            create_event('click', start + timedelta(hours=2 + idx * 0.3))
            create_event('submit', start + timedelta(hours=3 + idx * 0.3))

    print('Created campaign:', campaign.id, campaign.name)
    print('Use this report URL: /admin/core/campaign-report/%d/' % campaign.id)

if __name__ == '__main__':
    main()
