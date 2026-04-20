# Fine-Grained Permissions Implementation Guide

## Overview
This document describes the implementation of fine-grained permissions for Django admin staff users in the phishing-platform project. These permissions allow granular control over what actions different staff members can perform.

## Permissions Implemented

### 1. **core.can_send_campaigns**
- **Description:** Can start / send campaigns (execute send action)
- **Models affected:** Campaign
- **Actions protected:**
  - `send_campaign_emails` action
  - `view_campaign_report` action
  - Campaign start via API endpoint
  - Email sending from campaign change form

### 2. **core.can_view_reports**
- **Description:** Can view campaign reports (see campaign results but not modify)
- **Models affected:** Campaign
- **Views protected:**
  - Campaign report page (`/admin/core/campaign/<id>/report/`)
  - Campaign report data API endpoint

### 3. **core.can_manage_targets**
- **Description:** Can add targets (import CSV, edit target list)
- **Models affected:** Target
- **Actions protected:**
  - Add/create targets
  - Edit/change targets
  - Delete targets
  - Import targets from CSV
  - Add targets to campaigns

### 4. **core.can_manage_email_templates**
- **Description:** Can edit email templates
- **Models affected:** EmailTemplate
- **Actions protected:**
  - Add/create email templates
  - Edit/change email templates
  - Delete email templates
  - Recalculate realism scores

### 5. **core.can_manage_landing_pages**
- **Description:** Can edit landing pages
- **Models affected:** LandingPage
- **Actions protected:**
  - Add/create landing pages
  - Edit/change landing pages
  - Delete landing pages

## Files Modified

### 1. **core/models.py**
Added custom permissions to model Meta classes:

```python
class Campaign(models.Model):
    # ... fields ...
    class Meta:
        permissions = [
            ('can_send_campaigns', 'Can start / send campaigns'),
            ('can_view_reports', 'Can view campaign reports'),
        ]

class EmailTemplate(models.Model):
    # ... fields ...
    class Meta:
        permissions = [
            ('can_manage_email_templates', 'Can edit email templates'),
        ]

class Target(models.Model):
    # ... fields ...
    class Meta:
        permissions = [
            ('can_manage_targets', 'Can add targets (import CSV, edit target list)'),
        ]

class LandingPage(models.Model):
    # ... fields ...
    class Meta:
        permissions = [
            ('can_manage_landing_pages', 'Can edit landing pages'),
        ]
```

### 2. **core/admin.py**
Major changes:

#### A. **CustomUserAdmin** (lines 22-44)
- Extended `BaseUserAdmin` from `django.contrib.auth.admin`
- Added helpful description in the "Permissions" fieldset
- Shows which permissions control which features
- Unregisters default User admin and registers custom one

```python
class CustomUserAdmin(BaseUserAdmin):
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Adds help text to Permissions fieldset
        # ...
```

#### B. **CampaignAdmin** (lines 95-110)
Added permission checks:
- `has_add_permission()` - Only superusers can create campaigns
- `has_change_permission()` - Only superusers can edit campaigns
- `has_delete_permission()` - Only superusers can delete campaigns
- `has_view_permission()` - All staff can view campaigns
- `view_campaign_report()` - Checks `core.can_view_reports`
- `send_campaign_emails()` - Checks `core.can_send_campaigns`
- `send_emails_view()` - Checks `core.can_send_campaigns`
- `start_campaign_view()` - Checks `core.can_send_campaigns`

#### C. **EmailTemplateAdmin** (lines 330-350)
Permission checks for email templates:
- `has_add_permission()` - Checks `core.can_manage_email_templates`
- `has_change_permission()` - Checks `core.can_manage_email_templates`
- `has_delete_permission()` - Checks `core.can_manage_email_templates`
- `has_view_permission()` - All staff can view

#### D. **TargetAdmin** (lines 373-438)
Permission checks for targets:
- `has_add_permission()` - Checks `core.can_manage_targets`
- `has_change_permission()` - Checks `core.can_manage_targets`
- `has_delete_permission()` - Checks `core.can_manage_targets`
- `has_view_permission()` - All staff can view
- `import_csv_view()` - Checks `core.can_manage_targets`
- `add_to_campaign()` - Checks `core.can_manage_targets`

#### E. **LandingPageAdmin** (lines 527-561)
Permission checks for landing pages:
- `has_add_permission()` - Checks `core.can_manage_landing_pages`
- `has_change_permission()` - Checks `core.can_manage_landing_pages`
- `has_delete_permission()` - Checks `core.can_manage_landing_pages`
- `has_view_permission()` - All staff can view

### 3. **core/views.py**
Added permission decorators:

#### A. Added imports (line 16)
```python
from functools import wraps
```

#### B. Added custom decorator (lines 22-32)
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

#### C. Protected views (around lines 298-313)
```python
@staff_member_required
@permission_required('core.can_view_reports')
def campaign_report_data(request, campaign_id=None):
    # ...

@staff_member_required
@permission_required('core.can_view_reports')
def campaign_report_view(request, campaign_id=None):
    # ...
```

### 4. **core/migrations/0016_alter_campaign_options_...**
Auto-generated migration that creates the custom permissions in the database.

## How to Use

### Assigning Permissions to Staff Users

1. **Go to Admin User Management**
   - Navigate to `/admin/auth/user/`
   - Click on a staff user to edit

2. **In the "Permissions" Section**
   - Find the custom permissions in the list:
     - `core | campaign | Can start / send campaigns`
     - `core | campaign | Can view campaign reports`
     - `core | target | Can add targets (...)`
     - `core | emailtemplate | Can manage email templates`
     - `core | landingpage | Can manage landing pages`

3. **Select Desired Permissions**
   - Check the boxes for permissions you want to grant
   - Click "Save"

### Permission Examples

#### Campaign Manager (Can send campaigns and view reports)
- ✅ core.campaign.can_send_campaigns
- ✅ core.campaign.can_view_reports
- ❌ core.target.can_manage_targets
- ❌ core.emailtemplate.can_manage_email_templates
- ❌ core.landingpage.can_manage_landing_pages

#### Content Manager (Can manage templates and landing pages)
- ❌ core.campaign.can_send_campaigns
- ✅ core.campaign.can_view_reports
- ✅ core.target.can_manage_targets
- ✅ core.emailtemplate.can_manage_email_templates
- ✅ core.landingpage.can_manage_landing_pages

#### Full Admin (Superuser - has all permissions automatically)
- ✅ All permissions (automatic for is_superuser=True)

## Permission Check Flow

### Admin Interface
1. **User tries to access admin page**
   ↓
2. **Django checks user.is_staff** (must be staff to access admin)
   ↓
3. **ModelAdmin.has_*_permission() methods called**
   - For add/change/delete: checks specific permission OR is_superuser
   - For view: checks if staff
   ↓
4. **Action methods check permissions**
   - If user doesn't have permission: error message shown
   - If user has permission: action proceeds

### Report Views
1. **User visits report URL**
   ↓
2. **@staff_member_required decorator checks is_staff**
   ↓
3. **@permission_required decorator checks user.has_perm()**
   ↓
4. **If no permission: redirects to /admin/ with error message**
   ↓
5. **If has permission: report rendered**

## Security Features

1. **Superuser Override**
   - Superusers (is_superuser=True) have all permissions automatically
   - No need to assign individual permissions to superusers

2. **Staff Requirement**
   - All admin and report views require is_staff=True
   - Users without staff status cannot access anything

3. **Granular Control**
   - Each action requires specific permission
   - No blanket "all or nothing" access
   - Cannot modify campaigns unless also have send_campaigns permission

4. **Action-Level Protection**
   - Custom actions check permissions
   - CSV import checks permissions
   - API endpoints check permissions
   - Form views check permissions

## Testing Permissions

### Via Django Shell
```python
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

# Create a test user
user = User.objects.get(username='testuser')

# Add specific permission
perm = Permission.objects.get(codename='can_send_campaigns')
user.user_permissions.add(perm)

# Check permission
user.has_perm('core.can_send_campaigns')  # Returns True/False
```

### Via Admin Interface
1. Create a new staff user
2. Edit the user
3. In the "Permissions" section, select desired permissions
4. Save
5. Log in as that user and verify they can/cannot perform actions

## Troubleshooting

### Permission denied error when trying to perform an action
1. **Check if user is staff**: User > Change user > Staff status checkbox
2. **Verify permission is assigned**: In user's permissions section
3. **Check superuser status**: If superuser=True, all permissions granted
4. **Clear browser cache**: Sometimes permissions aren't reflected immediately

### Custom permission not appearing in admin
1. **Run migrations**: `python manage.py migrate core`
2. **Restart Django server**
3. **Check models.py**: Verify Meta permissions are defined
4. **Check migration**: Run `python manage.py showmigrations core`

### Error "You do not have permission"
1. **Verify permission assignment**: Edit user in admin
2. **Check permission name**: Should match codename in models.py
3. **Superuser test**: Assign superuser=True to test user (should work)
4. **Check has_perm() call**: In admin code

## Future Enhancements

1. **Group-based Permissions**
   - Assign permissions to groups instead of individual users
   - Users inherit group permissions

2. **Role-based Access Control (RBAC)**
   - Define roles: "Campaign Manager", "Content Manager", etc.
   - Assign permissions to roles, then assign roles to users

3. **Object-level Permissions**
   - Allow user to send only specific campaigns
   - Restrict target imports by department

4. **Audit Logging**
   - Log who performed which actions and when
   - Maintain audit trail for compliance

## References

- Django Permission System: https://docs.djangoproject.com/en/5.0/topics/auth/default/
- Django Admin: https://docs.djangoproject.com/en/5.0/ref/contrib/admin/
- Custom Decorators: https://docs.djangoproject.com/en/5.0/topics/http/decorators/

---

**Last Updated:** April 20, 2026  
**Implementation Version:** 1.0  
**Django Version:** 5.0+  
**Python Version:** 3.8+
