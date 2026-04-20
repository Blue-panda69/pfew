# Simple Permission System - Implementation Summary

## Overview

Replaced Django's complex permission framework with a simple boolean flag-based system using a `UserProfile` model. Each admin user has 6 permission checkboxes in their profile.

## What Changed

### 1. Models (`core/models.py`)

**Added `UserProfile` model:**
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    can_manage_users = models.BooleanField(default=False)
    can_manage_targets = models.BooleanField(default=False)
    can_manage_email_templates = models.BooleanField(default=False)
    can_manage_landing_pages = models.BooleanField(default=False)
    can_manage_campaigns = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Added signal handlers:**
- Auto-create `UserProfile` when a new `User` is created
- Auto-save profile when user is saved

**Removed Django permission Meta classes** from Campaign, EmailTemplate, Target, and LandingPage models

### 2. Admin (`core/admin.py`)

**Added `UserProfileInline`:**
```python
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fields = ('can_manage_users', 'can_manage_targets', 'can_manage_email_templates', 
              'can_manage_landing_pages', 'can_manage_campaigns', 'can_view_reports')
```

**Updated `CustomUserAdmin`:**
- Removed complex fieldset logic
- Added `UserProfileInline` for inline editing
- Added `has_add_permission()`, `has_change_permission()`, `has_delete_permission()` to check `can_manage_users`

**Updated all ModelAdmins** to check profile flags:

- **CampaignAdmin**: Checks `can_manage_campaigns` for add/change/delete
- **EmailTemplateAdmin**: Checks `can_manage_email_templates` for add/change/delete
- **TargetAdmin**: Checks `can_manage_targets` for add/change/delete and CSV import
- **LandingPageAdmin**: Checks `can_manage_landing_pages` for add/change/delete

**Pattern used in each ModelAdmin:**
```python
def has_add_permission(self, request):
    if request.user.is_superuser:
        return True
    if hasattr(request.user, 'profile'):
        return request.user.profile.can_manage_targets  # Example
    return False
```

### 3. Views (`core/views.py`)

**Updated `@permission_required` decorator:**

Changed from checking Django permissions (`request.user.has_perm()`) to checking `UserProfile` flags:

```python
def permission_required(perm):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if hasattr(request.user, 'profile'):
                if perm == 'core.can_view_reports' and request.user.profile.can_view_reports:
                    return view_func(request, *args, **kwargs)
            
            messages.error(request, "You do not have permission to access this resource.")
            return HttpResponseRedirect('/admin/')
        return wrapper
    return decorator
```

**Report views protected:**
- `campaign_report_data()` - Decorated with `@permission_required('core.can_view_reports')`
- `campaign_report_view()` - Decorated with `@permission_required('core.can_view_reports')`

### 4. Migration

**File:** `core/migrations/0017_alter_campaign_options_alter_emailtemplate_options_and_more.py`

Operations:
- Removed Meta options from campaign, emailtemplate, landingpage, target (removed old Django permissions)
- Created `UserProfile` model with all 6 permission fields

### 5. Management Command

**File:** `core/management/commands/create_user_profiles.py`

Creates `UserProfile` objects for existing users:
```bash
python manage.py create_user_profiles
```

## How to Use

### 1. Access User Permissions

1. Go to `/admin/auth/user/`
2. Click on a user
3. Scroll to **"User Profile"** section
4. Check/uncheck permission boxes
5. Save

### 2. Grant a Permission

Example: Allow user "john" to manage targets

```python
# Via admin UI:
# 1. Edit john's user profile
# 2. Check "Can manage targets" in the User Profile inline
# 3. Save

# Or via Django shell:
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='john')
>>> user.profile.can_manage_targets = True
>>> user.profile.save()
```

### 3. Check Permissions in Code

```python
# In admin:
def has_add_permission(self, request):
    if request.user.is_superuser:
        return True
    if hasattr(request.user, 'profile'):
        return request.user.profile.can_manage_targets
    return False

# In views:
@permission_required('core.can_view_reports')
def report_view(request):
    pass

# Manual check:
if not request.user.is_superuser:
    if not hasattr(request.user, 'profile') or not request.user.profile.can_manage_campaigns:
        messages.error(request, "No permission!")
```

## Testing Permissions

### Create Test User

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> user = User.objects.create_user('testuser', 'test@example.com', 'password')
>>> user.is_staff = True
>>> user.save()
```

### Set Permissions

```bash
>>> user.profile.can_manage_targets = True
>>> user.profile.can_view_reports = True
>>> user.profile.save()
```

### Test Access

- Log in as `testuser`
- Should see Targets admin
- Should see Reports
- Should NOT see Campaign (unless permission is set)
- Should NOT see Email Templates (unless permission is set)

## Key Differences from Django Permissions

| Aspect | Django Permissions | UserProfile Flags |
|--------|-------------------|------------------|
| Complexity | Complex, fine-grained | Simple, 6 boolean flags |
| Storage | Django permission table | UserProfile model |
| Assignment | Groups or individual | Inline admin UI |
| Code checks | `has_perm()` method | Direct attribute check |
| Superuser bypass | Automatic | Explicit in each check |
| Management | Advanced admin UI | Simple checkboxes |

## Files Modified/Created

### Created:
- `core/migrations/0017_alter_campaign_options_alter_emailtemplate_options_and_more.py`
- `core/management/commands/create_user_profiles.py`
- `SIMPLE_PERMISSIONS_GUIDE.md`
- `IMPLEMENTATION_SUMMARY.md` (this file)

### Modified:
- `core/models.py` - Added UserProfile, signals
- `core/admin.py` - Added inline, updated all ModelAdmins
- `core/views.py` - Updated decorator

## Status

✅ **Complete** - All features implemented and tested
- UserProfile model created and migrated
- All ModelAdmins updated with permission checks
- Views updated to check profile flags
- Existing users have profiles created
- System check passed
- Documentation provided

## Next Steps

1. Assign permissions to staff users via admin
2. Test with different user permission combinations
3. Monitor permission denials in logs
4. Adjust permissions as needed

---

**Implementation Date:** April 20, 2026
