import re

from django.db import models
from django.contrib.auth.models import User
from ckeditor_uploader.fields import RichTextUploadingField
import uuid
import re

TRACKING_INJECTION_MARKER = '<!-- TRACKING_INJECTED_BY_SYSTEM -->'


def _contains_any(text: str, patterns):
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(pattern.lower() in lower for pattern in patterns)


def _unique_keywords(text: str, keywords):
    if not isinstance(text, str):
        return []
    found = set()
    lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in lower:
            found.add(keyword.lower())
    return sorted(found)


def _has_all_caps_word(text: str):
    if not isinstance(text, str):
        return False
    return bool(re.search(r'\b[A-Z]{2,}\b', text))


def _has_raw_ip_in_href(text: str):
    if not isinstance(text, str):
        return False
    return bool(re.search(r'href=["\"](https?://)?\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/|["\"])', text, flags=re.IGNORECASE))


def _has_url_shortener(text: str):
    if not isinstance(text, str):
        return False
    shorteners = ['bit.ly', 'tinyurl', 't.co', 'goo.gl', 'ow.ly', 'buff.ly', 'shorturl.at', 'is.gd']
    lower = text.lower()
    return any(short in lower for short in shorteners)


def _has_descriptive_link_text(html: str):
    if not isinstance(html, str):
        return False
    phrases = [
        'verify your account', 'check your account', 'secure your account', 'confirm your account',
        'vérifiez votre compte', 'confirmez votre compte', 'sécurisez votre compte', 'vérifiez maintenant',
        'review your account', 'update your information', 'mettre à jour votre compte'
    ]
    anchors = re.findall(r'<a[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
    for anchor_text in anchors:
        cleaned = re.sub(r'\s+', ' ', anchor_text).strip().lower()
        if any(phrase in cleaned for phrase in phrases):
            return True
    return False


def _has_image_tag(html: str):
    if not isinstance(html, str):
        return False
    return bool(re.search(r'<img\s+[^>]*src=', html, flags=re.IGNORECASE))


def _has_css_present(html: str):
    if not isinstance(html, str):
        return False
    return bool(re.search(r'style\s*=|<style\b', html, flags=re.IGNORECASE))


def _contains_common_misspelling(text: str):
    if not isinstance(text, str):
        return False
    misspellings = ['teh', 'recieve', 'adress', 'occured', 'definately', 'seperate', 'wich', 'thier', 'goverment', 'beleive']
    lower = text.lower()
    return any(misspelling in lower for misspelling in misspellings)


def instrument_landing_page_html(content: str) -> str:
    if not isinstance(content, str):
        return content

    if TRACKING_INJECTION_MARKER in content:
        return content

    # Only inject if the page contains links, buttons, submits, or forms
    if not re.search(r'<(?:a\b|button\b|input\b[^>]*\btype\s*=\s*(?:["\']?(?:submit|button|image)["\']?)|form\b)',
                    content, flags=re.IGNORECASE):
        return content

    script = '''\n{}\n<script>
(function() {{
    function getTargetParam() {{
        var params = new URLSearchParams(window.location.search);
        return params.get('target');
    }}
    function getSubmitEndpoint() {{
        var path = window.location.pathname.replace(/\/$/, '');
        return path + '/submit/';
    }}
    function sendTracking(data) {{
        var endpoint = getSubmitEndpoint();
        var target = getTargetParam();
        if (target) {{
            endpoint += '?target=' + encodeURIComponent(target);
        }}
        fetch(endpoint, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json'
            }},
            body: JSON.stringify(data)
        }}).finally(function() {{
            window.location.href = 'https://www.google.com';
        }});
    }}
    function attachLinkTracking() {{
        document.querySelectorAll('a').forEach(function(link) {{
            if (link.dataset.trackingAttached) return;
            link.dataset.trackingAttached = '1';
            link.addEventListener('click', function(event) {{
                event.preventDefault();
                sendTracking({{
                    event: 'link_click',
                    href: this.href,
                    text: this.innerText || ''
                }});
            }});
        }});
    }}
    function attachButtonTracking() {{
        document.querySelectorAll('button, input[type=button], input[type=submit], input[type=image]').forEach(function(button) {{
            if (button.dataset.trackingAttached) return;
            button.dataset.trackingAttached = '1';
            button.addEventListener('click', function(event) {{
                event.preventDefault();
                sendTracking({{
                    event: 'button_click',
                    value: this.value || this.innerText || '',
                    type: this.type || ''
                }});
            }});
        }});
    }}
    function attachFormTracking() {{
        document.querySelectorAll('form').forEach(function(form) {{
            if (form.dataset.trackingAttached) return;
            form.dataset.trackingAttached = '1';
            form.addEventListener('submit', function(event) {{
                event.preventDefault();
                var formData = new FormData(form);
                var data = {{ event: 'form_submit', fields: {{}} }};
                formData.forEach(function(value, key) {{
                    data.fields[key] = value;
                }});
                sendTracking(data);
            }});
        }});
    }}
    function initTracking() {{
        attachLinkTracking();
        attachButtonTracking();
        attachFormTracking();
    }}
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initTracking);
    }} else {{
        initTracking();
    }}
}})();
</script>\n'''.format(TRACKING_INJECTION_MARKER)

    if re.search(r'</body\s*>', content, flags=re.IGNORECASE):
        content = re.sub(r'(</body\s*>)', script + r'\1', content, flags=re.IGNORECASE)
    else:
        content = content + script

    return content


class SmtpAccount(models.Model):
    email = models.EmailField(max_length=254, unique=True)
    password = models.CharField(max_length=255, help_text='Gmail app password')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('finished', 'Finished'),
    ]
    name = models.CharField(max_length=200)
    sender_account = models.ForeignKey('SmtpAccount', on_delete=models.PROTECT)
    description = models.TextField(blank=True)
    email_template = models.ForeignKey('EmailTemplate', null=True, blank=True, on_delete=models.SET_NULL)
    landing_page = models.ForeignKey('LandingPage', null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = (
            ("start_campaign", "Can start campaign"),
            ("view_campaign_report", "Can view campaign report"),
            ("send_campaign_emails", "Can send campaign emails"),
        )

    def __str__(self):
        return self.name

class EmailTemplate(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200, default="Important Security Update Required")
    realism_score = models.IntegerField(default=0, help_text='Automatically computed realism score from 0 to 100.')
    # Replace TextField with RichTextUploadingField
    html_content = RichTextUploadingField(default="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Security Alert</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4;">
    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #333; margin: 0;">🔒 Security Alert</h1>
        </div>
        
        <p style="font-size: 16px; line-height: 1.6; color: #555;">
            Dear {{ first_name }} {{ last_name }},
        </p>
        
        <p style="font-size: 16px; line-height: 1.6; color: #555;">
            Our IT security team has detected a potential security vulnerability that requires immediate attention. 
            To ensure the safety of your account and prevent unauthorized access, we need you to verify your credentials.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ tracking_link }}" style="background-color: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                Verify Your Account Now
            </a>
        </div>
        
        <p style="font-size: 14px; line-height: 1.6; color: #777; border-top: 1px solid #eee; padding-top: 20px; margin-top: 30px;">
            If you did not request this verification, please contact IT support immediately.
        </p>
        
        <p style="font-size: 12px; color: #999; text-align: center; margin-top: 20px;">
            This is an automated security notification. Please do not reply to this email.
        </p>
    </div>
    
    <!-- Tracking pixel -->
    <img src="{{ tracking_pixel }}" style="display: none;" alt="">
</body>
</html>
""")
    plain_text_content = models.TextField(blank=True, default="""
SECURITY ALERT

Dear {{ first_name }} {{ last_name }},

Our IT security team has detected a potential security vulnerability that requires immediate attention. 
To ensure the safety of your account and prevent unauthorized access, we need you to verify your credentials.

Please click the link below to verify your account:
{{ tracking_link }}

If you did not request this verification, please contact IT support immediately.

This is an automated security notification. Please do not reply to this email.
""")
    variables = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def compute_realism_score(self) -> int:
        score = 0
        html = self.html_content or ''
        subject = self.subject or ''
        combined_text = f"{subject}\n{html}"
        all_text = f"{subject}\n{html}\n{self.plain_text_content or ''}"

        # Personalization
        if _contains_any(all_text, ['{{ first_name }}', '{{ last_name }}']):
            score += 15
        if not _contains_any(all_text, ['dear user', 'cher utilisateur']):
            score += 5

        # Urgency / call-to-action
        urgency_keywords = [
            'urgent', 'immediately', 'verify now', 'account locked', 'suspended', 'security alert',
            'immédiatement', 'vérifiez maintenant', 'compte bloqué', 'suspendu', 'alerte de sécurité'
        ]
        unique_keywords = _unique_keywords(combined_text, urgency_keywords)
        score += min(len(unique_keywords) * 5, 20)

        # Professional language & grammar
        if not _has_all_caps_word(all_text):
            score += 5
        if (all_text.count('!') or 0) <= 2:
            score += 5
        if not _contains_common_misspelling(all_text):
            score += 10

        # Link believability
        if _has_descriptive_link_text(html):
            score += 10
        if not _has_raw_ip_in_href(html):
            score += 5
        if not _has_url_shortener(html):
            score += 5

        # Visual credibility
        if _has_image_tag(html):
            score += 10
        if _has_css_present(html):
            score += 10

        return max(0, min(score, 100))

    def save(self, *args, **kwargs):
        self.realism_score = self.compute_realism_score()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Target(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    # Optional groups (e.g., "IT", "HR") – we can expand later
    groups = models.CharField(max_length=200, blank=True, help_text="Comma-separated group names")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.email

class CampaignTarget(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('campaign', 'target')
    
    def __str__(self):
        return f"{self.campaign.name} -> {self.target.email}"

class TrackingEvent(models.Model):
    EVENT_TYPES = [
        ('open', 'Email opened'),
        ('click', 'Link clicked'),
        ('submit', 'Form submitted'),
        ('report', 'Email reported'),
    ]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.target.email} - {self.event_type} at {self.timestamp}"
class PendingClick(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.campaign.name} - {self.target.email} - {self.token}"

class PendingOpen(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    target = models.ForeignKey(Target, on_delete=models.CASCADE)
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.campaign.name} - {self.target.email} - {self.tracking_id}"
    
class EmailImage(models.Model):
    name = models.CharField(max_length=100, help_text="Descriptive name")
    image = models.ImageField(upload_to='email_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def url(self):
        return self.image.url

class LandingPage(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, help_text="URL slug for the landing page")
    content = models.TextField(
        blank=True,
        default="""
<div class="landing-page-wrapper">
    <h1>Security Update Required</h1>
    <p>Use the editor to build the page visually instead of writing raw HTML.</p>
    <p>Add text, images and links directly from CKEditor.</p>
</div>
""".strip(),
        help_text="Raw HTML content for the landing page. Stored exactly as entered.",
    )
    css_content = models.TextField(
        blank=True,
        default="""
/* Default landing page styling */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    margin: 0;
    padding: 20px;
    min-height: 100vh;
}

.landing-page-wrapper {
    max-width: 900px;
    margin: 0 auto;
    background: white;
    border-radius: 12px;
    box-shadow: 0 20px 45px rgba(0,0,0,0.12);
    padding: 40px;
}

.landing-page-wrapper h1 {
    font-size: 32px;
    margin-bottom: 20px;
    color: #2d3e50;
}

.landing-page-wrapper p {
    font-size: 16px;
    line-height: 1.75;
    color: #4a4a4a;
}

img {
    max-width: 100%;
    height: auto;
}
""".strip(),
        help_text="Raw CSS content for the landing page. Stored exactly as entered.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.title.lower().replace(' ', '-').replace('_', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title