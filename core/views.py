import uuid
import json
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from django.template import Template, Context
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models.functions import TruncDate, TruncHour
from .models import Campaign, TrackingEvent, CampaignTarget, Target, LandingPage, PendingClick, PendingOpen
from collections import OrderedDict
from datetime import timedelta

# 1x1 transparent pixel (base64 encoded GIF)
PIXEL = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

@csrf_exempt
def track_pixel(request, tracking_id):
    pending_open = PendingOpen.objects.filter(tracking_id=tracking_id).first()
    if not pending_open:
        # If the pixel is requested again after the first record,
        # allow the existing open event to still return the pixel.
        tracking_event = TrackingEvent.objects.filter(tracking_id=tracking_id, event_type='open').first()
        if not tracking_event:
            return HttpResponse(status=404)
    else:
        # Create the actual open event only when the pixel loads.
        tracking_event, created = TrackingEvent.objects.get_or_create(
            campaign=pending_open.campaign,
            target=pending_open.target,
            event_type='open',
            tracking_id=pending_open.tracking_id
        )
        if created:
            if request.META.get('HTTP_X_FORWARDED_FOR'):
                ip = request.META.get('HTTP_X_FORWARDED_FOR').split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            tracking_event.ip_address = ip
            tracking_event.user_agent = request.META.get('HTTP_USER_AGENT', '')
            tracking_event.save()
        pending_open.delete()

    # Return transparent pixel
    return HttpResponse(PIXEL, content_type='image/gif')



def track_click(request, token):
    # Look up the pending click by token
    pending = get_object_or_404(PendingClick, token=token)
    campaign = pending.campaign
    target = pending.target

    # Create the actual click event
    event = TrackingEvent.objects.create(
        campaign=campaign,
        target=target,
        event_type='click'
    )
    # Record IP and user agent
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    event.ip_address = ip
    event.user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
    event.save()

    # If the email was clicked but no open event exists yet, record it now.
    if not TrackingEvent.objects.filter(campaign=campaign, target=target, event_type='open').exists():
        pending_open = PendingOpen.objects.filter(campaign=campaign, target=target).first()
        tracking_id = pending_open.tracking_id if pending_open else None
        open_event = TrackingEvent.objects.create(
            campaign=campaign,
            target=target,
            event_type='open',
            tracking_id=tracking_id if tracking_id else uuid.uuid4(),
            ip_address=ip,
            user_agent=event.user_agent,
        )
        if pending_open:
            pending_open.delete()
        open_event.save()

    # Delete the pending click record (one-time use)
    pending.delete()
    
    # Redirect to landing page if campaign has one, otherwise redirect to Google
    if campaign.landing_page:
        landing_page_url = f"/landing-page/{campaign.landing_page.slug}/?target={target.id}"
        return HttpResponseRedirect(landing_page_url)
    else:
        return HttpResponseRedirect('https://www.google.com')


def _unique_event_count(campaign, event_type):
    return TrackingEvent.objects.filter(campaign=campaign, event_type=event_type).values('target_id').distinct().count()


def get_campaign_stats(campaign):
    total_sent = CampaignTarget.objects.filter(campaign=campaign, sent_at__isnull=False).count()
    stats = {
        'campaign_name': campaign.name,
        'campaign_id': campaign.id,
        'total_sent': total_sent,
        'unique_opens': _unique_event_count(campaign, 'open'),
        'unique_clicks': _unique_event_count(campaign, 'click'),
        'unique_submissions': _unique_event_count(campaign, 'submit'),
        'unique_reports': _unique_event_count(campaign, 'report'),
    }
    if total_sent:
        stats['open_rate'] = round(stats['unique_opens'] / total_sent * 100, 2)
        stats['click_rate'] = round(stats['unique_clicks'] / total_sent * 100, 2)
        stats['submission_rate'] = round(stats['unique_submissions'] / total_sent * 100, 2)
        stats['report_rate'] = round(stats['unique_reports'] / total_sent * 100, 2)
    else:
        stats['open_rate'] = stats['click_rate'] = stats['submission_rate'] = stats['report_rate'] = 0.0
    return stats


def get_campaign_target_count(campaign):
    return CampaignTarget.objects.filter(campaign=campaign).values('target_id').distinct().count()


def get_campaign_funnel_data(campaign):
    total_targets = get_campaign_target_count(campaign)
    unique_opens = _unique_event_count(campaign, 'open')
    unique_clicks = _unique_event_count(campaign, 'click')
    unique_submissions = _unique_event_count(campaign, 'submit')

    did_not_open = max(total_targets - unique_opens, 0)
    opened_only = max(unique_opens - unique_clicks, 0)
    clicked_only = max(unique_clicks - unique_submissions, 0)
    submitted_all = max(unique_submissions, 0)

    return {
        'labels': ['Did not open', 'Opened only', 'Clicked only', 'Submitted all'],
        'counts': [did_not_open, opened_only, clicked_only, submitted_all],
    }


def get_campaign_evolution_data(campaign, interval='hour'):
    total_targets = get_campaign_target_count(campaign)
    if total_targets == 0:
        return {'labels': [], 'open_rates': [], 'click_rates': []}

    now = timezone.now()
    if interval == 'day':
        start = now - timedelta(days=28)
        trunc_field = TruncDate('timestamp')
        bucket_format = '%Y-%m-%d'
        bucket_delta = timedelta(days=1)
        current = start.date()
        end = now.date()
    else:
        start = now - timedelta(hours=24)
        trunc_field = TruncHour('timestamp')
        bucket_format = '%Y-%m-%d %H:%M'
        bucket_delta = timedelta(hours=1)
        current = start.replace(minute=0, second=0, microsecond=0)
        end = now.replace(minute=0, second=0, microsecond=0)

    event_qs = TrackingEvent.objects.filter(
        campaign=campaign,
        event_type__in=['open', 'click'],
        timestamp__gte=start
    ).annotate(bucket=trunc_field).values('bucket', 'event_type', 'target_id').distinct()

    buckets = OrderedDict()
    while current <= end:
        buckets[current] = {'open': set(), 'click': set()}
        current += bucket_delta

    for item in event_qs:
        bucket = item['bucket']
        event_type = item['event_type']
        target_id = item['target_id']
        if bucket not in buckets:
            continue
        buckets[bucket][event_type].add(target_id)

    labels = []
    open_rates = []
    click_rates = []
    for bucket, counts in buckets.items():
        labels.append(bucket.strftime(bucket_format))
        open_rates.append(round(len(counts['open']) / total_targets * 100, 2))
        click_rates.append(round(len(counts['click']) / total_targets * 100, 2))

    return {'labels': labels, 'open_rates': open_rates, 'click_rates': click_rates}


def get_target_action_rows(campaign):
    campaign_targets = CampaignTarget.objects.filter(campaign=campaign).select_related('target')
    target_events = TrackingEvent.objects.filter(campaign=campaign).values('target_id', 'event_type').distinct()
    event_map = {}
    for item in target_events:
        target_id = item['target_id']
        event_map.setdefault(target_id, set()).add(item['event_type'])

    rows = []
    for campaign_target in campaign_targets:
        target = campaign_target.target
        events = event_map.get(target.id, set())
        rows.append({
            'target_id': target.id,
            'email': target.email,
            'name': f"{target.first_name} {target.last_name}".strip() or target.email,
            'opened': 'yes' if 'open' in events else 'no',
            'clicked': 'yes' if 'click' in events else 'no',
            'submitted': 'yes' if 'submit' in events else 'no',
            'reported': 'yes' if 'report' in events else 'no',
            'sent': 'yes' if campaign_target.sent_at else 'no',
        })
    return rows


def get_campaign_evolution(campaign):
    total_sent = CampaignTarget.objects.filter(campaign=campaign, sent_at__isnull=False).count()
    if not total_sent:
        return {'labels': [], 'open_rates': [], 'click_rates': []}

    event_qs = TrackingEvent.objects.filter(campaign=campaign, event_type__in=['open', 'click'])
    event_qs = event_qs.annotate(day=TruncDate('timestamp')).values('day', 'event_type', 'target_id').distinct()
    daily = {}
    for item in event_qs:
        day = item['day']
        event_type = item['event_type']
        target_id = item['target_id']
        daily.setdefault(day, {'open': set(), 'click': set()})[event_type].add(target_id)

    if daily:
        start_date = min(daily.keys())
        end_date = max(daily.keys())
    else:
        start_date = campaign.start_date.date() if campaign.start_date else None
        end_date = campaign.end_date.date() if campaign.end_date else start_date

    labels = []
    open_rates = []
    click_rates = []
    current = start_date
    while current and current <= end_date:
        counts = daily.get(current, {'open': set(), 'click': set()})
        labels.append(current.strftime('%Y-%m-%d'))
        open_rates.append(round(len(counts['open']) / total_sent * 100, 2))
        click_rates.append(round(len(counts['click']) / total_sent * 100, 2))
        current += timedelta(days=1)

    return {'labels': labels, 'open_rates': open_rates, 'click_rates': click_rates}


def get_comparison_campaigns(campaign_ids):
    campaigns = Campaign.objects.filter(id__in=campaign_ids)
    campaigns_by_id = {campaign.id: campaign for campaign in campaigns}
    comparison = []
    for cid in campaign_ids:
        campaign = campaigns_by_id.get(cid)
        if not campaign:
            continue
        stats = get_campaign_stats(campaign)
        comparison.append({
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'open_rate': stats['open_rate'],
            'click_rate': stats['click_rate'],
            'submission_rate': stats['submission_rate'],
            'report_rate': stats['report_rate'],
        })
    return comparison


@staff_member_required
def campaign_report_data(request, campaign_id=None):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    interval = request.GET.get('interval', 'hour')
    if interval not in ['hour', 'day']:
        interval = 'hour'

    data = get_campaign_evolution_data(campaign, interval)
    return JsonResponse(data)


@staff_member_required
def campaign_report_view(request, campaign_id=None):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    metrics = get_campaign_stats(campaign)
    target_action_rows = get_target_action_rows(campaign)

    compare_ids_param = request.GET.get('compare_ids', '')
    comparison_campaigns = []
    if compare_ids_param:
        extra_ids = [int(cid) for cid in compare_ids_param.split(',') if cid.strip().isdigit()]
        combined_ids = []
        for cid in [campaign_id] + extra_ids:
            if cid not in combined_ids:
                combined_ids.append(cid)
        comparison_campaigns = get_comparison_campaigns(combined_ids)

    if request.method == 'POST':
        reported_target_ids = {
            int(target_id)
            for target_id in request.POST.getlist('reported_targets')
            if target_id.isdigit()
        }
        campaign_target_ids = list(campaign.campaigntarget_set.values_list('target_id', flat=True))

        for target_id in campaign_target_ids:
            has_report = TrackingEvent.objects.filter(
                campaign=campaign,
                target_id=target_id,
                event_type='report'
            ).exists()
            if target_id in reported_target_ids and not has_report:
                TrackingEvent.objects.create(
                    campaign=campaign,
                    target_id=target_id,
                    event_type='report',
                    ip_address='',
                    user_agent='manual update',
                )
            elif target_id not in reported_target_ids and has_report:
                TrackingEvent.objects.filter(
                    campaign=campaign,
                    target_id=target_id,
                    event_type='report'
                ).delete()
        messages.success(request, 'Reported status updated successfully.')
        target_action_rows = get_target_action_rows(campaign)

    funnel_data = get_campaign_funnel_data(campaign)
    context = {
        'campaign': campaign,
        'metrics': metrics,
        'target_action_rows': target_action_rows,
        'metric_labels': ['Open Rate', 'Click Rate', 'Submission Rate', 'Report Rate'],
        'metric_values': [metrics['open_rate'], metrics['click_rate'], metrics['submission_rate'], metrics['report_rate']],
        'funnel_labels': funnel_data['labels'],
        'funnel_values': funnel_data['counts'],
        'comparison_campaigns': comparison_campaigns,
    }

    return render(request, 'admin/campaign_report.html', context)


def phishing_blog_fr(request):
    final_path = Path(settings.BASE_DIR) / 'phishing-blog-fr.html'
    if not final_path.exists():
        return HttpResponse('Final page not found.', status=404)
    return HttpResponse(final_path.read_text(encoding='utf-8'), content_type='text/html')


def landing_page_view(request, slug):
    """Render a landing page from HTML and CSS content"""
    landing_page = get_object_or_404(LandingPage, slug=slug)

    # Get target from URL parameter
    target_id = request.GET.get('target')

    target = None

    # Try to get target from URL parameter
    if target_id:
        try:
            target = Target.objects.get(id=target_id)
        except Target.DoesNotExist:
            target = None

    # Get campaign from landing page relationship
    campaign = landing_page.campaign_set.first()

    # Prepare context for template rendering with target data
    context_data = {
        'first_name': target.first_name if target else '',
        'last_name': target.last_name if target else '',
        'email': target.email if target else '',
        'Email': target.email if target else '',
        'Department': target.department if target else '',
        'Groups': target.groups if target else '',
        'tracking_pixel': '',
        'tracking_link': '',
    }

    # Render landing page content with Django template variables
    html_template = Template(landing_page.content)
    rendered_html = html_template.render(Context(context_data))

    context = {
        'landing_page': landing_page,
        'html_content': rendered_html,
        'css_content': landing_page.css_content,
        'target': target,
        'campaign': campaign,
    }

    return render(request, 'landing_page.html', context)

@csrf_exempt
def landing_page_form_submit(request, slug):
    """Handle form submissions from landing pages"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    landing_page = get_object_or_404(LandingPage, slug=slug)
    campaign = landing_page.campaign_set.first()

    # Extract form data
    form_data = {}
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            form_data = json.loads(request.body)
        except json.JSONDecodeError:
            form_data = {}
    else:
        form_data = dict(request.POST.items())

    # Ignore empty submissions
    if not any(str(value).strip() for value in form_data.values()):
        return JsonResponse({'success': False, 'message': 'Please fill out the form before submitting.'}, status=400)

    target = None
    target_id = request.GET.get('target')
    if target_id:
        try:
            target = Target.objects.get(id=target_id)
        except Target.DoesNotExist:
            target = None

    # Create tracking event for form submission
    if campaign:
        if not target and 'email' in form_data:
            try:
                target = Target.objects.get(email=form_data['email'])
            except Target.DoesNotExist:
                pass

        TrackingEvent.objects.create(
            campaign=campaign,
            target=target,
            event_type='submit',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    # Log form submission data
    print(f"Form submission for {slug}: {form_data}")

    return JsonResponse({
        'success': True,
        'message': 'Form submitted successfully'
    })