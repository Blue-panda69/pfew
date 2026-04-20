from django.contrib import admin
from django.contrib import messages
from django import forms
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Permission
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
import csv
import io
from .models import Campaign, EmailTemplate, Target, CampaignTarget, TrackingEvent, PendingClick, LandingPage, SmtpAccount
from .forms import CampaignTargetBulkForm, CampaignForm, SmtpAccountForm, LandingPageForm
from .utils import send_phishing_email
from .models import EmailImage

admin.site.register(EmailImage)
admin.site.register(PendingClick)


PERMISSION_TABLE_MODELS = [
    ("Target", "core", "target", ["view", "add", "change", "delete"]),
    ("Users", "auth", "user", ["view", "add", "change", "delete"]),
    ("Campaign", "core", "campaign", ["view", "add", "change", "delete"]),
    ("Email template", "core", "emailtemplate", ["view", "add", "change", "delete"]),
    ("Landing page", "core", "landingpage", ["view", "add", "change", "delete"]),
    ("SMTP account", "core", "smtpaccount", ["view", "add", "change", "delete"]),
    ("User history", "admin", "logentry", ["view"]),
]

PERMISSION_TABLE_ACTIONS = ["view", "add", "change", "delete"]

EXTRA_PERMISSION_ENTRIES = [
    ("Campaign actions", "core", "campaign", "start_campaign"),
    ("Campaign actions", "core", "campaign", "send_campaign_emails"),
    ("Campaign actions", "core", "campaign", "view_campaign_report"),
]

ACTION_LABELS = {
    "view": "View",
    "add": "Add",
    "change": "Edit",
    "delete": "Delete",
    "start_campaign": "Start campaign",
    "send_campaign_emails": "Send campaign emails",
    "view_campaign_report": "View report",
}


def _resolve_permission(app_label, model_name, codename):
    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        return None
    return Permission.objects.filter(content_type=content_type, codename=codename).first()


def _build_simple_permission_choices():
    choices = []
    managed_ids = []

    matrix_rows = []
    for label, app_label, model_name, row_actions in PERMISSION_TABLE_MODELS:
        row = {"label": label, "cells": []}
        for action in PERMISSION_TABLE_ACTIONS:
            if action not in row_actions:
                row["cells"].append({"action": action, "perm_id": None, "label": ACTION_LABELS[action]})
                continue
            codename = f"{action}_{model_name}"
            perm = _resolve_permission(app_label, model_name, codename)
            if not perm:
                row["cells"].append({"action": action, "perm_id": None, "label": ACTION_LABELS[action]})
                continue
            managed_ids.append(perm.id)
            row["cells"].append({"action": action, "perm_id": perm.id, "label": ACTION_LABELS[action]})
            choices.append((str(perm.id), f"{label} - {ACTION_LABELS[action]}"))
        matrix_rows.append(row)

    extras = []
    for section, app_label, model_name, codename in EXTRA_PERMISSION_ENTRIES:
        perm = _resolve_permission(app_label, model_name, codename)
        if not perm:
            continue
        managed_ids.append(perm.id)
        label = ACTION_LABELS.get(codename, codename.replace("_", " ").title())
        extras.append({"section": section, "perm_id": perm.id, "label": label})
        choices.append((str(perm.id), f"{section} - {label}"))

    return choices, managed_ids, matrix_rows, extras


class PermissionMatrixWidget(forms.CheckboxSelectMultiple):
    def __init__(self, matrix_rows=None, extras=None, attrs=None):
        super().__init__(attrs)
        self.matrix_rows = matrix_rows or []
        self.extras = extras or []

    def render(self, name, value, attrs=None, renderer=None):
        selected = {str(v) for v in (value or [])}
        table_rows = []
        for row in self.matrix_rows:
            cells_html = []
            for cell in row["cells"]:
                perm_id = cell["perm_id"]
                if not perm_id:
                    cells_html.append('<td class="perm-off">-</td>')
                    continue
                checked = ' checked="checked"' if str(perm_id) in selected else ""
                input_id = f"id_{name}_{perm_id}"
                cells_html.append(
                    f'<td><label class="perm-check" for="{escape(input_id)}">'
                    f'<input type="checkbox" id="{escape(input_id)}" name="{escape(name)}" value="{perm_id}"{checked}>'
                    f"</label></td>"
                )
            table_rows.append(
                f"<tr><th>{escape(row['label'])}</th>{''.join(cells_html)}</tr>"
            )

        extra_html = ""
        if self.extras:
            chunks = ['<div class="perm-extra-section"><div class="perm-extra-title">Campaign actions</div><div class="perm-extra-grid">']
            for entry in self.extras:
                perm_id = entry["perm_id"]
                checked = ' checked="checked"' if str(perm_id) in selected else ""
                input_id = f"id_{name}_{perm_id}"
                chunks.append(
                    f'<label class="perm-extra-item" for="{escape(input_id)}">'
                    f'<input type="checkbox" id="{escape(input_id)}" name="{escape(name)}" value="{perm_id}"{checked}>'
                    f"<span>{escape(entry['label'])}</span></label>"
                )
            chunks.append("</div></div>")
            extra_html = "".join(chunks)

        html = (
            '<div class="permission-matrix">'
            '<table class="permission-matrix-table">'
            "<thead><tr><th>Module</th><th>See</th><th>Add</th><th>Edit</th><th>Delete</th></tr></thead>"
            f"<tbody>{''.join(table_rows)}</tbody>"
            "</table>"
            f"{extra_html}"
            "</div>"
        )
        return mark_safe(html)


class SimplePermissionMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices, managed_ids, matrix_rows, extras = _build_simple_permission_choices()
        self.fields["simple_permissions"].choices = choices
        self.fields["simple_permissions"].widget = PermissionMatrixWidget(matrix_rows=matrix_rows, extras=extras)
        self._managed_permission_ids = set(managed_ids)
        if self.instance and self.instance.pk:
            assigned = self.instance.user_permissions.filter(id__in=self._managed_permission_ids).values_list("id", flat=True)
            self.initial["simple_permissions"] = [str(pk) for pk in assigned]

    def _save_simple_permissions(self, user):
        selected_ids = {int(pk) for pk in self.cleaned_data.get("simple_permissions", [])}
        to_remove = user.user_permissions.filter(id__in=self._managed_permission_ids)
        user.user_permissions.remove(*to_remove)
        if selected_ids:
            to_add = Permission.objects.filter(id__in=selected_ids)
            user.user_permissions.add(*to_add)


class SimpleUserCreationForm(SimplePermissionMixin, UserCreationForm):
    simple_permissions = forms.MultipleChoiceField(
        required=False,
        label="Access permissions",
        widget=forms.CheckboxSelectMultiple,
        help_text="Select what this user can access.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active", "is_staff")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self._save_simple_permissions(user)
        return user


class SimpleUserChangeForm(SimplePermissionMixin, UserChangeForm):
    simple_permissions = forms.MultipleChoiceField(
        required=False,
        label="Access permissions",
        widget=forms.CheckboxSelectMultiple,
        help_text="Select what this user can access.",
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self._save_simple_permissions(user)
        return user


admin.site.unregister(User)


@admin.register(User)
class SimpleUserAdmin(DjangoUserAdmin):
    add_form = SimpleUserCreationForm
    form = SimpleUserChangeForm
    filter_horizontal = ("groups",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "simple_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "first_name", "last_name", "email", "is_active", "is_staff", "groups", "simple_permissions"),
        }),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        managed_ids = getattr(form, "_managed_permission_ids", set())
        selected_ids = {int(pk) for pk in form.cleaned_data.get("simple_permissions", [])}
        if managed_ids:
            user.user_permissions.remove(*user.user_permissions.filter(id__in=managed_ids))
        if selected_ids:
            user.user_permissions.add(*Permission.objects.filter(id__in=selected_ids))


def _history_action_label(action_flag):
    if action_flag == ADDITION:
        return "Added"
    if action_flag == CHANGE:
        return "Changed"
    if action_flag == DELETION:
        return "Deleted"
    return "Action"


def user_history_view(request):
    if not request.user.has_perm("admin.view_logentry"):
        raise PermissionDenied

    users = User.objects.filter(is_active=True).order_by("username")
    selected_user_id = request.GET.get("user_id", "all")

    entries = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")
    if selected_user_id and selected_user_id != "all":
        entries = entries.filter(user_id=selected_user_id)

    recent_entries = []
    for entry in entries[:300]:
        recent_entries.append({
            "username": entry.user.get_username() if entry.user else "Unknown",
            "action": _history_action_label(entry.action_flag),
            "object": entry.object_repr or "-",
            "model": entry.content_type.name if entry.content_type else "Unknown content",
            "time": entry.action_time,
            "change_message": entry.change_message or "",
        })

    context = {
        **admin.site.each_context(request),
        "title": "Users history",
        "users": users,
        "selected_user_id": selected_user_id,
        "entries": recent_entries,
        "is_all_history": selected_user_id == "all",
    }
    return render(request, "admin/core/user_history.html", context)


_original_admin_get_urls = admin.site.get_urls


def _custom_admin_get_urls():
    custom_urls = [
        path("core/user-history/", admin.site.admin_view(user_history_view), name="core_user_history"),
    ]
    return custom_urls + _original_admin_get_urls()


admin.site.get_urls = _custom_admin_get_urls


class SmtpAccountAdmin(admin.ModelAdmin):
    form = SmtpAccountForm
    list_display = ['email', 'is_active', 'created_at']
    search_fields = ['email']
    fieldsets = (
        ('Informations du compte Gmail', {
            'fields': ('email', 'password'),
            'description': '<div style="background-color: #e8f4f8; border: 1px solid #417690; padding: 12px; '
                          'border-radius: 4px; margin-bottom: 20px; font-size: 13px;"'
                          'style="color: #113329;">'
                          '<strong>⚠️ Important :</strong> N\'utilisez pas votre mot de passe Gmail habituel. '
                          'Vous devez générer un <strong>mot de passe d\'application</strong> depuis votre compte Google. '
                          'Les instructions détaillées sont affichées dans le champ ci-dessous.'
                          '</div>'
        }),
        ('Paramètres', {
            'fields': ('is_active',),
        }),
    )

admin.site.register(SmtpAccount, SmtpAccountAdmin)

# ======================
# Custom bulk delete action (works for all models)
# ======================
def bulk_delete_selected(modeladmin, request, queryset):
    count = queryset.delete()[0]
    messages.success(request, f'Successfully deleted {count} item(s).')
bulk_delete_selected.short_description = "Delete selected items"


# ======================
# CampaignTarget inline so campaign can include targets on the same page
# ======================
class CampaignTargetInline(admin.TabularInline):
    model = CampaignTarget
    extra = 1
    raw_id_fields = ('target',)
    fk_name = 'campaign'


# ======================
# Campaign Admin
# ======================
class CampaignAdmin(admin.ModelAdmin):
    form = CampaignForm
    change_form_template = "admin/core/campaign/change_form.html"
    change_list_template = "admin/core/campaign/change_list.html"
    actions = ['send_campaign_emails', 'view_campaign_report']
    list_display = ['name', 'sender_account', 'status', 'start_date', 'end_date', 'time_until_start', 'running_time', 'report_link']

    START_PERMISSION = "core.start_campaign"
    REPORT_PERMISSION = "core.view_campaign_report"
    SEND_EMAIL_PERMISSION = "core.send_campaign_emails"

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm(self.SEND_EMAIL_PERMISSION):
            actions.pop('send_campaign_emails', None)
        if not request.user.has_perm(self.REPORT_PERMISSION):
            actions.pop('view_campaign_report', None)
        return actions

    def changelist_view(self, request, extra_context=None):
        self.request_for_list_display = request
        self._refresh_campaign_statuses(request)
        extra_context = extra_context or {}
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'targets' in form.cleaned_data:
            selected_targets = set(form.cleaned_data['targets'])
            existing_targets = set(obj.campaigntarget_set.select_related('target').values_list('target', flat=True))
            new_target_ids = {t.id for t in selected_targets}

            to_add = new_target_ids - existing_targets
            to_remove = existing_targets - new_target_ids

            for target_id in to_add:
                CampaignTarget.objects.get_or_create(campaign=obj, target_id=target_id)

            if to_remove:
                CampaignTarget.objects.filter(campaign=obj, target_id__in=to_remove).delete()

        if obj.email_template and obj.start_date and obj.start_date <= timezone.now():
            self._send_campaign_now(request, obj)

    def _format_timedelta(self, delta):
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"

    def time_until_start(self, obj):
        now = timezone.now()
        if obj.status == 'draft':
            start_url = reverse('admin:core_campaign_start_now', args=[obj.pk])
            if obj.start_date > now:
                return format_html(
                    '<span class="campaign-countdown" data-start="{}" data-url="{}" data-pk="{}">{}</span>',
                    obj.start_date.isoformat(), start_url, obj.pk, self._format_timedelta(obj.start_date - now)
                )
            return format_html(
                '<span class="campaign-countdown" data-start="{}" data-url="{}" data-pk="{}">Due now</span>',
                obj.start_date.isoformat(), start_url, obj.pk
            )
        return '--'
    time_until_start.short_description = 'Starts In'

    def running_time(self, obj):
        now = timezone.now()
        if obj.status == 'running':
            elapsed = now - obj.start_date
            return format_html(
                '<span class="campaign-runtime" data-start="{}" data-status="running">{}</span>',
                obj.start_date.isoformat(), self._format_timedelta(elapsed)
            )
        if obj.status == 'finished':
            elapsed = obj.end_date - obj.start_date
            return format_html(
                '<span class="campaign-runtime" data-start="{}" data-end="{}" data-status="finished">{}</span>',
                obj.start_date.isoformat(), obj.end_date.isoformat(), self._format_timedelta(elapsed)
            )
        return '--'
    running_time.short_description = 'Running Time'

    def report_link(self, obj):
        if not hasattr(self, "request_for_list_display") or not self.request_for_list_display.user.has_perm(self.REPORT_PERMISSION):
            return '--'
        url = reverse('core:admin_campaign_report', args=[obj.pk])
        return format_html('<a class="button" href="{}">Report</a>', url)
    report_link.short_description = 'Report'
    report_link.allow_tags = True

    def _send_campaign_now(self, request, campaign):
        if not campaign.email_template:
            self.message_user(request, f"Campaign '{campaign.name}' has no email template and cannot start.", level=messages.WARNING)
            return

        targets = CampaignTarget.objects.filter(campaign=campaign).select_related('target')
        if not targets.exists():
            self.message_user(request, f"Campaign '{campaign.name}' has no targets and was skipped.", level=messages.WARNING)
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
            try:
                send_phishing_email(campaign, ct.target, campaign.email_template)
                ct.sent_at = timezone.now()
                ct.save()
                sent_count += 1
            except Exception as e:
                fail_count += 1
                self.message_user(request, f"Failed to send to {ct.target.email}: {str(e)}", level=messages.ERROR)

        if campaign.status == 'running':
            self.message_user(request, f"Campaign '{campaign.name}' started automatically and is now running: {sent_count} sent, {fail_count} failed.")
        else:
            self.message_user(request, f"Campaign '{campaign.name}' started and finished immediately: {sent_count} sent, {fail_count} failed.")

    def _refresh_campaign_statuses(self, request):
        if not request.user.has_perm(self.START_PERMISSION):
            return
        now = timezone.now()
        due_campaigns = Campaign.objects.filter(status='draft', start_date__lte=now, email_template__isnull=False)
        for campaign in due_campaigns:
            self._send_campaign_now(request, campaign)

        finished_campaigns = Campaign.objects.filter(status='running', end_date__lte=now)
        for campaign in finished_campaigns:
            campaign.status = 'finished'
            campaign.save(update_fields=['status'])

    def start_campaign_view(self, request, campaign_id):
        if not request.user.has_perm(self.START_PERMISSION):
            return JsonResponse({'started': False, 'error': 'Permission denied.'}, status=403)
        campaign = Campaign.objects.filter(id=campaign_id).first()
        if not campaign:
            return JsonResponse({'started': False, 'error': 'Campaign not found.'}, status=404)
        if campaign.status != 'draft':
            return JsonResponse({'started': False, 'error': 'Campaign cannot be started because it is not in draft status.'}, status=400)

        now = timezone.now()
        if campaign.start_date > now:
            campaign.start_date = now
            campaign.save(update_fields=['start_date'])

        self._send_campaign_now(request, campaign)
        return JsonResponse({'started': True})

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send-emails/<int:campaign_id>/', self.send_emails_view, name='send_campaign_emails'),
            path('start-now/<int:campaign_id>/', self.start_campaign_view, name='core_campaign_start_now'),
        ]
        return custom_urls + urls

    def view_campaign_report(self, request, queryset):
        if not request.user.has_perm(self.REPORT_PERMISSION):
            messages.error(request, "You do not have permission to view campaign reports.")
            return HttpResponseRedirect(request.get_full_path())
        if queryset.count() != 1:
            messages.error(request, "Please select exactly one campaign.")
            return HttpResponseRedirect(request.get_full_path())
        campaign = queryset.first()
        return redirect(reverse('core:admin_campaign_report', args=[campaign.id]))
    view_campaign_report.short_description = "View campaign report (select one campaign)"

    def send_campaign_emails(self, request, queryset):
        if not request.user.has_perm(self.SEND_EMAIL_PERMISSION):
            messages.error(request, "You do not have permission to send campaign emails.")
            return HttpResponseRedirect(request.get_full_path())
        # This action is triggered when one or more campaigns are selected.
        # We only support one campaign at a time for simplicity.
        if queryset.count() != 1:
            messages.error(request, "Please select exactly one campaign.")
            return HttpResponseRedirect(request.get_full_path())
        campaign = queryset.first()
        return redirect(reverse('admin:send_campaign_emails', args=[campaign.id]))
    send_campaign_emails.short_description = "Send campaign emails (select one campaign)"

    def send_emails_view(self, request, campaign_id):
        if not request.user.has_perm(self.SEND_EMAIL_PERMISSION):
            messages.error(request, "You do not have permission to send campaign emails.")
            return redirect('admin:core_campaign_changelist')
        from .models import Target
        campaign = Campaign.objects.get(id=campaign_id)
        targets = CampaignTarget.objects.filter(campaign=campaign).select_related('target')
        if not targets:
            messages.error(request, f'Campaign "{campaign.name}" has no associated targets.')
            return redirect('admin:core_campaign_changelist')

        if request.method == 'POST':
            template_id = request.POST.get('email_template')
            if not template_id:
                messages.error(request, "Please select an email template.")
                return redirect(request.path)
            template = EmailTemplate.objects.get(id=template_id)
            sent_count = 0
            fail_count = 0
            for ct in targets:
                try:
                    send_phishing_email(campaign, ct.target, template)
                    ct.sent_at = timezone.now()
                    ct.save()
                    sent_count += 1
                except Exception as e:
                    fail_count += 1
                    messages.error(request, f"Failed to send to {ct.target.email}: {str(e)}")
            messages.success(request, f"Emails sent: {sent_count} successful, {fail_count} failed.")
            return redirect('admin:core_campaign_changelist')

        # GET request: show form to choose email template
        templates = EmailTemplate.objects.all()
        if not templates:
            messages.error(request, "No email templates found. Please create one first.")
            return redirect('admin:core_campaign_changelist')
        return render(request, 'admin/send_campaign_emails.html', {
            'campaign': campaign,
            'targets': targets,
            'templates': templates,
            'target_count': targets.count(),
        })

# ======================
# EmailTemplate Admin
# ======================
class EmailTemplateAdmin(admin.ModelAdmin):
    actions = [bulk_delete_selected, 'recalculate_realism_scores']
    list_display = ['name', 'subject', 'realism_score_badge', 'created_at']
    readonly_fields = ['realism_score']
    change_form_template = "admin/emailtemplate/change_form.html"
    fields = ['name', 'subject', 'html_content', 'realism_score']

    def realism_score_badge(self, obj):
        score = getattr(obj, 'realism_score', 0)
        if score >= 80:
            color = '#198754'  # green
        elif score >= 50:
            color = '#ffc107'  # yellow
        else:
            color = '#dc3545'  # red
        return format_html(
            '<span style="display:inline-block; min-width:40px; padding:2px 8px; border-radius:12px; color:#fff; background:{}; font-weight:600;">{}</span>',
            color,
            score
        )
    realism_score_badge.short_description = 'Realism'
    realism_score_badge.admin_order_field = 'realism_score'

    def recalculate_realism_scores(self, request, queryset):
        updated = 0
        for template in queryset:
            template.realism_score = template.compute_realism_score()
            template.save(update_fields=['realism_score'])
            updated += 1
        self.message_user(request, f"Recalculated realism score for {updated} template(s).")
    recalculate_realism_scores.short_description = 'Recalculate realism scores for selected templates'

# ======================
# Target Admin with CSV import and bulk add to campaign
# ======================
class TargetAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'department', 'groups']
    search_fields = ['email', 'first_name', 'last_name']
    actions = [bulk_delete_selected, 'add_to_campaign']
    change_list_template = "admin/target_changelist.html"  # for CSV upload button

    # ---------- CSV import ----------
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv_view, name='import_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request, queryset):
        return HttpResponseRedirect('import-csv/')
    import_csv.short_description = "Import targets from CSV"

    def import_csv_view(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, "No file selected.")
                return redirect('.')

            data = csv_file.read().decode('utf-8')
            io_string = io.StringIO(data)
            reader = csv.DictReader(io_string)
            created_count = 0
            updated_count = 0

            for row in reader:
                email = row.get('email')
                if not email:
                    continue
                defaults = {
                    'first_name': row.get('first_name', ''),
                    'last_name': row.get('last_name', ''),
                    'department': row.get('department', ''),
                    'groups': row.get('groups', ''),
                }
                obj, created = Target.objects.update_or_create(email=email, defaults=defaults)
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            messages.success(request, f"Imported: {created_count} created, {updated_count} updated.")
            return redirect('../../')

        # GET – show upload form
        return render(request, 'csv_upload.html', {'title': 'Import Targets from CSV'})

    # ---------- Bulk add to campaign ----------
    def add_to_campaign(self, request, queryset):
        if 'campaign_id' in request.POST:
            campaign_id = request.POST.get('campaign_id')
            campaign = Campaign.objects.get(id=campaign_id)
            count = 0
            for target in queryset:
                obj, created = CampaignTarget.objects.get_or_create(campaign=campaign, target=target)
                if created:
                    count += 1
            messages.success(request, f'Added {count} targets to campaign "{campaign.name}".')
            return HttpResponseRedirect(request.get_full_path())
        # Render intermediate page to select campaign
        return render(request, 'admin/add_to_campaign.html', {
            'targets': queryset,
            'campaigns': Campaign.objects.all(),
        })
    add_to_campaign.short_description = "Add selected targets to a campaign"


# ======================
# CampaignTarget Admin
# ======================

class CampaignTargetAdmin(admin.ModelAdmin):
    actions = [bulk_delete_selected]
    list_display = ['campaign', 'target', 'sent_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add-bulk/', self.add_bulk_view, name='campaign_target_add_bulk'),
        ]
        return custom_urls + urls

    def add_bulk_view(self, request):
        from .models import Target
        if request.method == 'POST':
            form = CampaignTargetBulkForm(request.POST)
            if form.is_valid():
                campaign = form.cleaned_data['campaign']
                targets = form.cleaned_data['targets']
                created_count = 0
                for target in targets:
                    obj, created = CampaignTarget.objects.get_or_create(campaign=campaign, target=target)
                    if created:
                        created_count += 1
                messages.success(request, f'Added {created_count} targets to campaign "{campaign.name}".')
                return HttpResponseRedirect(reverse('admin:core_campaigntarget_changelist'))
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = CampaignTargetBulkForm()

        targets = Target.objects.all().values('id', 'email', 'first_name', 'last_name', 'department', 'groups')
        return render(request, 'admin/campaigntarget_add_bulk.html', {
            'form': form,
            'targets': targets,
            'title': 'Add multiple targets to campaign',
        })

    def add_view(self, request, form_url='', extra_context=None):
        return redirect('admin:campaign_target_add_bulk')




# ======================
# TrackingEvent Admin
# ======================
class TrackingEventAdmin(admin.ModelAdmin):
    actions = [bulk_delete_selected]
    list_display = ['target', 'event_type', 'timestamp', 'campaign']
    list_filter = ['event_type', 'campaign', 'timestamp']
    search_fields = ['target__email', 'tracking_id']


# ======================
# LandingPage Admin
# ======================
class LandingPageAdmin(admin.ModelAdmin):
    actions = [bulk_delete_selected]
    list_display = ['title', 'slug', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    form = LandingPageForm
    change_form_template = "admin/core/landingpage/change_form.html"
    fieldsets = (
        ('Page details', {
            'fields': ('title', 'slug'),
        }),
        ('Content', {
            'fields': ('content',),
            'description': 'Editable landing page HTML/body content.',
        }),
        ('CSS styling', {
            'fields': ('css_content',),
            'description': 'Separate CSS styling for the landing page.',
        }),
    )


# ======================
# Register all models
# ======================
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(Target, TargetAdmin)
admin.site.register(TrackingEvent, TrackingEventAdmin)
admin.site.register(LandingPage, LandingPageAdmin)