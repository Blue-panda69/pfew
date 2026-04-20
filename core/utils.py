import re
from django.core.mail import EmailMessage, get_connection
from django.template import Template, Context
from django.conf import settings
from .models import PendingOpen, PendingClick

def generate_tracking_links(campaign, target, base_url='http://127.0.0.1:8000'):
    # Open event is only recorded when the pixel loads.
    pending_open = PendingOpen.objects.create(campaign=campaign, target=target)
    pending_click = PendingClick.objects.create(campaign=campaign, target=target)
    pixel_url = f"{base_url}/api/track/pixel/{pending_open.tracking_id}/"
    click_url = f"{base_url}/api/track/click/{pending_click.token}/"
    return {
        'pixel_url': pixel_url,
        'click_url': click_url,
        'open_tracking_id': str(pending_open.tracking_id),
        'click_token': str(pending_click.token),
    }


def inject_tracking_link(html_message, tracking_link):
    if not html_message or not tracking_link:
        return html_message

    pattern = re.compile(r'(<a\b[^>]*\bhref\s*=\s*)(["\'])(.*?)(\2)', flags=re.IGNORECASE)
    def replace_href(match):
        prefix = match.group(1)
        quote = match.group(2)
        return f"{prefix}{quote}{tracking_link}{quote}"

    new_html, count = pattern.subn(replace_href, html_message, count=1)
    return new_html if count else html_message


def inject_tracking_pixel(html_message, pixel_url):
    if not html_message or not pixel_url:
        return html_message

    if pixel_url in html_message:
        return html_message

    pixel_html = f'<img src="{pixel_url}" style="display:none;width:1px;height:1px;max-height:1px;max-width:1px;" alt="" />'
    if re.search(r'</body\s*>', html_message, flags=re.IGNORECASE):
        return re.sub(r'(</body\s*>)', pixel_html + r'\1', html_message, flags=re.IGNORECASE)
    return html_message + pixel_html


def send_phishing_email(campaign, target, email_template, base_url=None):
    if base_url is None:
        base_url = getattr(settings, 'TRACKING_BASE_URL', 'http://127.0.0.1:8000')
    # Generate unique tracking links for this target
    tracking = generate_tracking_links(campaign, target, base_url)

    # Prepare dynamic variables with target-specific data
    context = {
        'first_name': target.first_name,
        'last_name': target.last_name,
        'email': target.email,
        'Email': target.email,  # Alternative capitalized version
        'Department': target.department,
        'Groups': target.groups,
        'tracking_pixel': tracking['pixel_url'],
        'tracking_link': tracking['click_url'],  # Click is tracked, then redirects to landing page
    }

    # Render HTML content with Django template variables
    html_template = Template(email_template.html_content)
    html_message = html_template.render(Context(context))

    # If the template did not explicitly use tracking_link, inject tracking into the first anchor.
    if campaign.landing_page and '{{ tracking_link }}' not in email_template.html_content:
        html_message = inject_tracking_link(html_message, tracking['click_url'])

    # Ensure the hidden open pixel is present so we can record opens even when the template
    # does not explicitly include {{ tracking_pixel }}.
    if '{{ tracking_pixel }}' not in email_template.html_content:
        html_message = inject_tracking_pixel(html_message, tracking['pixel_url'])

    # Send email using the campaign-specific sender account
    if not hasattr(campaign, 'sender_account') or campaign.sender_account is None:
        raise ValueError('Campaign has no sender account configured. Please assign an active SmtpAccount to this campaign.')

    connection = get_connection(
        backend=settings.EMAIL_BACKEND,
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=campaign.sender_account.email,
        password=campaign.sender_account.password,
        use_tls=settings.EMAIL_USE_TLS,
    )

    message = EmailMessage(
        subject=email_template.subject,
        body=html_message,
        from_email=campaign.sender_account.email,
        to=[target.email],
        connection=connection,
    )
    message.content_subtype = 'html'
    message.send(fail_silently=False)
    
    # Mark as sent in CampaignTarget (optional – we'll implement later)
    return True