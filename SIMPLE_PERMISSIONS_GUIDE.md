# Simple Permission System for Django Admin Users

## Overview

This system provides a simple, boolean flag-based permission system for Django admin staff users. Instead of using Django's complex permission framework, each admin user has a `UserProfile` model with 6 boolean fields that control access to different parts of the admin interface.

## Permission Flags

Each `UserProfile` has the following boolean fields (all default to `False`):

1. **can_manage_users** - Can add/edit/delete other admin users
2. **can_manage_targets** - Can add/edit/delete targets and import CSV files
3. **can_manage_email_templates** - Can add/edit/delete email templates
4. **can_manage_landing_pages** - Can add/edit/delete landing pages
5. **can_manage_campaigns** - Can create/edit campaigns and send emails
6. **can_view_reports** - Can view campaign reports (read-only access)

## How It Works

### UserProfile Model

Located in `core/models.py`, the `UserProfile` model has a `OneToOneField` to Django's `User` model:

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    can_manage_users = models.BooleanField(default=False)
    can_manage_targets = models.BooleanField(default=False)
    can_manage_email_templates = models.BooleanField(default=False)
    can_manage_landing_pages = models.BooleanField(default=False)
    can_manage_campaigns = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    # ... timestamps
```

### Auto-creation of UserProfile

A Django signal handler automatically creates a `UserProfile` when a new `User` is created:

```python
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
```

This means every user automatically gets a profile with all permissions set to `False` by default.

### Admin Interface

#### Managing Users and Permissions

1. Go to `/admin/auth/user/`
2. Click on any user to edit
3. Scroll down to the **"User Profile"** section (inline form)
4. Check/uncheck the permission boxes as needed
5. Click **Save**

**Example:** To allow a user to manage targets:
- Edit the user
- Check the "Can manage targets" box in the User Profile section
- Save

#### Superusers

Superusers bypass all permission checks and always have full access to all features. No need to configure their profiles.

## Permission Checks in Admin

Each `ModelAdmin` class checks permissions in the following methods:

```python
def has_add_permission(self, request):
    if request.user.is_superuser:
        return True
    if hasattr(request.user, 'profile'):
        return request.user.profile.can_manage_targets  # Example
    return False

def has_change_permission(self, request, obj=None):
    # Same pattern
    
def has_delete_permission(self, request, obj=None):
    # Same pattern
```

### Updated ModelAdmins

- **UserAdmin** - Checks `can_manage_users`
- **TargetAdmin** - Checks `can_manage_targets` (including CSV import)
- **EmailTemplateAdmin** - Checks `can_manage_email_templates`
- **LandingPageAdmin** - Checks `can_manage_landing_pages`
- **CampaignAdmin** - Checks `can_manage_campaigns` (including "send emails" action)

### Report Views

The campaign report views use a decorator to check `can_view_reports`:

```python
@staff_member_required
@permission_required('core.can_view_reports')
def campaign_report_view(request, campaign_id=None):
    # ... view logic
```

The `@permission_required` decorator checks the `UserProfile.can_view_reports` flag.

## Setup Instructions

### 1. Apply Migrations

The migration has already been generated and applied. If you need to reapply:

```bash
python manage.py migrate core
```

### 2. Create UserProfiles for Existing Users

If there are existing users without profiles, run:

```bash
python manage.py create_user_profiles
```

This creates a `UserProfile` for each user in the system.

### 3. Configure User Permissions

1. Go to `/admin/auth/user/`
2. Select a staff user
3. In the "User Profile" inline section, check the boxes for the permissions they need
4. Save

### 4. Test

- Log in as a non-superuser staff member
- Verify they can only access the sections their profile allows

## File Changes Summary

### New Files
- `core/migrations/0017_...py` - Migration for UserProfile
- `core/management/commands/create_user_profiles.py` - Management command to create profiles

### Modified Files
- `core/models.py` - Added UserProfile model and signal handlers
- `core/admin.py` - Added UserProfileInline, updated all ModelAdmin classes
- `core/views.py` - Updated @permission_required decorator

## Troubleshooting

### User Cannot Access a Feature

1. Verify the user is a staff member (has `is_staff=True`)
2. Check that the user's profile has the correct permission flag enabled
3. If the user is a superuser, they always have access

### "You do not have permission" Messages

These appear when a user without the required flag tries to perform an action. The permission checks are in:
- `has_add_permission()` - Adding new items
- `has_change_permission()` - Editing items
- `has_delete_permission()` - Deleting items
- Custom action methods (e.g., `send_campaign_emails()`)

### Signal Handler Not Creating Profiles

Make sure `core.apps.CoreConfig` is in `INSTALLED_APPS` and signal handlers are connected properly. Verify with:

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from core.models import UserProfile
>>> u = User.objects.first()
>>> u.profile  # Should return the profile
```

## Security Notes

- All permission checks verify `is_superuser` first and bypass checks if True
- All ModelAdmin methods that modify data check permissions
- Custom actions that send emails or import files all check permissions
- Report views are protected by the `@permission_required` decorator
- Staff member status (`is_staff=True`) is still required for admin access

## Future Enhancements

Possible extensions to this system:

1. Add timestamps to track when permissions were last modified
2. Add an audit log to track permission changes
3. Create permission groups for bulk assignment
4. Add a management command to bulk-assign permissions
5. Create a custom admin action to bulk-update permissions

---

**Last Updated:** April 20, 2026
