# Code Changes Summary

## Overview of Implementation

This document provides a quick reference of all code changes made for fine-grained permissions implementation.

---

## 1. core/models.py - Permission Definitions

### Campaign Model
```python
class Campaign(models.Model):
    # ... existing fields ...
    
    class Meta:
        permissions = [
            ('can_send_campaigns', 'Can start / send campaigns'),
            ('can_view_reports', 'Can view campaign reports'),
        ]
```

### EmailTemplate Model
```python
class EmailTemplate(models.Model):
    # ... existing fields ...
    
    class Meta:
        permissions = [
            ('can_manage_email_templates', 'Can edit email templates'),
        ]
```

### Target Model
```python
class Target(models.Model):
    # ... existing fields ...
    
    class Meta:
        permissions = [
            ('can_manage_targets', 'Can add targets (import CSV, edit target list)'),
        ]
```

### LandingPage Model
```python
class LandingPage(models.Model):
    # ... existing fields ...
    
    class Meta:
        permissions = [
            ('can_manage_landing_pages', 'Can edit landing pages'),
        ]
```

---

## 2. core/admin.py - Permission Enforcement

### Import Changes
```python
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
```

### CustomUserAdmin (NEW)
```python
class CustomUserAdmin(BaseUserAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Adds helpful description to Permissions fieldset
        for i, (name, options) in enumerate(fieldsets):
            if name == 'Permissions':
                new_options = dict(options)
                new_options['description'] = (
                    'Assign specific permissions to control staff user access:<br/>'
                    '<ul style="margin-top: 10px;">'
                    '<li><strong>Can manage users:</strong> core | user | Can create other users</li>'
                    '<li><strong>Can send campaigns:</strong> core | campaign | Can send campaigns</li>'
                    '<li><strong>Can view reports:</strong> core | campaign | Can view reports</li>'
                    '<li><strong>Can manage targets:</strong> core | target | Can manage targets</li>'
                    '<li><strong>Can manage email templates:</strong> core | emailtemplate | Can manage templates</li>'
                    '<li><strong>Can manage landing pages:</strong> core | landingpage | Can manage pages</li>'
                    '</ul>'
                )
                fieldsets[i] = (name, new_options)
                break
        return fieldsets

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
```

### CampaignAdmin - Permission Checks
```python
class CampaignAdmin(admin.ModelAdmin):
    # ... existing config ...
    
    # ======================
    # Permission checks
    # ======================
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def view_campaign_report(self, request, queryset):
        if queryset.count() != 1:
            messages.error(request, "Please select exactly one campaign.")
            return HttpResponseRedirect(request.get_full_path())
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_view_reports') and not request.user.is_superuser:
            messages.error(request, "You do not have permission to view campaign reports.")
            return HttpResponseRedirect(request.get_full_path())
        campaign = queryset.first()
        return redirect(reverse('core:admin_campaign_report', args=[campaign.id]))

    def send_campaign_emails(self, request, queryset):
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_send_campaigns') and not request.user.is_superuser:
            messages.error(request, "You do not have permission to send campaigns.")
            return HttpResponseRedirect(request.get_full_path())
        if queryset.count() != 1:
            messages.error(request, "Please select exactly one campaign.")
            return HttpResponseRedirect(request.get_full_path())
        campaign = queryset.first()
        return redirect(reverse('admin:send_campaign_emails', args=[campaign.id]))

    def send_emails_view(self, request, campaign_id):
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_send_campaigns') and not request.user.is_superuser:
            messages.error(request, "You do not have permission to send campaigns.")
            return HttpResponseRedirect(reverse('admin:core_campaign_changelist'))
        # ... rest of view ...

    def start_campaign_view(self, request, campaign_id):
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_send_campaigns') and not request.user.is_superuser:
            return JsonResponse({'started': False, 'error': 'You do not have permission.'}, status=403)
        # ... rest of view ...
```

### EmailTemplateAdmin - Permission Checks
```python
class EmailTemplateAdmin(admin.ModelAdmin):
    # ... existing config ...
    
    # ======================
    # Permission checks
    # ======================
    def has_add_permission(self, request):
        return request.user.has_perm('core.can_manage_email_templates') or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_email_templates') or request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_email_templates') or request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff
```

### TargetAdmin - Permission Checks
```python
class TargetAdmin(admin.ModelAdmin):
    # ... existing config ...
    
    # ======================
    # Permission checks
    # ======================
    def has_add_permission(self, request):
        return request.user.has_perm('core.can_manage_targets') or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_targets') or request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_targets') or request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def import_csv_view(self, request):
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_manage_targets') and not request.user.is_superuser:
            messages.error(request, "You do not have permission to import targets.")
            return redirect('admin:core_target_changelist')
        # ... rest of view ...

    def add_to_campaign(self, request, queryset):
        # CHECK PERMISSION
        if not request.user.has_perm('core.can_manage_targets') and not request.user.is_superuser:
            messages.error(request, "You do not have permission to add targets to campaigns.")
            return HttpResponseRedirect(request.get_full_path())
        # ... rest of action ...
```

### LandingPageAdmin - Permission Checks
```python
class LandingPageAdmin(admin.ModelAdmin):
    # ... existing config ...
    
    # ======================
    # Permission checks
    # ======================
    def has_add_permission(self, request):
        return request.user.has_perm('core.can_manage_landing_pages') or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_landing_pages') or request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('core.can_manage_landing_pages') or request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff
```

---

## 3. core/views.py - Permission Decorators

### New Imports
```python
from functools import wraps
```

### New Permission Decorator
```python
def permission_required(perm):
    """
    Decorator to check if user has a specific permission or is a superuser.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.has_perm(perm):
                return view_func(request, *args, **kwargs)
            messages.error(request, f"You do not have permission to access this resource.")
            return HttpResponseRedirect('/admin/')
        return wrapper
    return decorator
```

### Protected Views
```python
@staff_member_required
@permission_required('core.can_view_reports')
def campaign_report_data(request, campaign_id=None):
    # ... existing code ...

@staff_member_required
@permission_required('core.can_view_reports')
def campaign_report_view(request, campaign_id=None):
    # ... existing code ...
```

---

## 4. core/migrations/0016_... - Auto-Generated

```python
# This was auto-generated by Django
# It adds the custom permissions to the database

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_...'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='campaign',
            options={'permissions': [('can_send_campaigns', 'Can start / send campaigns'), 
                                     ('can_view_reports', 'Can view campaign reports')]},
        ),
        migrations.AlterModelOptions(
            name='emailtemplate',
            options={'permissions': [('can_manage_email_templates', 'Can edit email templates')]},
        ),
        migrations.AlterModelOptions(
            name='landingpage',
            options={'permissions': [('can_manage_landing_pages', 'Can edit landing pages')]},
        ),
        migrations.AlterModelOptions(
            name='target',
            options={'permissions': [('can_manage_targets', 'Can add targets (import CSV, edit target list)')]},
        ),
    ]
```

---

## Summary of Changes

| File | Lines Changed | Type | Purpose |
|------|---------------|------|---------|
| `core/models.py` | 4 sections | Added Meta | Define custom permissions |
| `core/admin.py` | 100+ | Added classes & methods | Enforce permissions in admin |
| `core/views.py` | 30+ | Added decorator & calls | Protect report views |
| `core/migrations/0016_...` | Auto-generated | Migration | Add permissions to DB |

---

## Testing the Implementation

### Unit Test Example
```python
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

class PermissionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', password='test123')
        self.user.is_staff = True
        self.user.save()

    def test_user_can_send_campaigns(self):
        perm = Permission.objects.get(codename='can_send_campaigns')
        self.user.user_permissions.add(perm)
        
        self.assertTrue(self.user.has_perm('core.can_send_campaigns'))

    def test_user_cannot_manage_templates_without_permission(self):
        self.assertFalse(self.user.has_perm('core.can_manage_email_templates'))
```

---

## Rollback Instructions (if needed)

```bash
# Reverse the migration
python manage.py migrate core 0015

# Or delete the migration file and recreate without permissions
rm core/migrations/0016_*.py
python manage.py makemigrations core
python manage.py migrate core
```

---

## Related Documentation

- [`PERMISSIONS_IMPLEMENTATION.md`](./PERMISSIONS_IMPLEMENTATION.md) - Full detailed guide
- [`QUICK_START_PERMISSIONS.md`](./QUICK_START_PERMISSIONS.md) - Quick reference
- [Django Permissions Docs](https://docs.djangoproject.com/en/5.0/topics/auth/default/)
