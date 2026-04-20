# Quick Start: Using Fine-Grained Permissions

## TL;DR - What Was Done

✅ **5 custom permissions** created  
✅ **Database migration** applied  
✅ **Admin interface** customized to show permissions  
✅ **Permission checks** added to all admin views and actions  
✅ **Report views** protected with permission decorators  

---

## Step 1: Run Migration (Already Done!)

```bash
# The migration has already been applied:
python manage.py migrate
```

**Migration file:** `core/migrations/0016_alter_campaign_options_...`

---

## Step 2: Assign Permissions to Users

### Via Django Admin (Recommended)

1. Go to `/admin/auth/user/`
2. Click on a **staff user** to edit
3. Scroll to **"Permissions"** section
4. Check the permissions you want to assign:
   - `core | campaign | Can start / send campaigns`
   - `core | campaign | Can view campaign reports`
   - `core | target | Can add targets (import CSV, edit target list)`
   - `core | emailtemplate | Can manage email templates`
   - `core | landingpage | Can manage landing pages`
5. Click **"Save"**

### Via Django Shell

```python
from django.contrib.auth.models import User, Permission

# Get the user
user = User.objects.get(username='john')

# Add permission by codename
perm = Permission.objects.get(codename='can_send_campaigns')
user.user_permissions.add(perm)

# Or add multiple permissions at once
perms = Permission.objects.filter(codename__in=[
    'can_send_campaigns',
    'can_view_reports',
    'can_manage_targets'
])
user.user_permissions.set(perms)

# Check if user has permission
print(user.has_perm('core.can_send_campaigns'))  # True or False
```

---

## Step 3: Test Permissions

### Test as Different User

1. **Create a test staff user** (if not exists)
   ```
   /admin/auth/user/add/
   - Username: testuser
   - Password: (set a password)
   - Staff status: ✅ CHECKED
   - Superuser status: ❌ UNCHECKED
   ```

2. **Assign specific permission**
   - Edit testuser
   - Add "Can start / send campaigns" permission
   - Save

3. **Log out and log back in as testuser**
   - Try to send a campaign → ✅ WORKS
   - Try to add email template → ❌ "Permission denied"

### Test as Superuser

1. Create a test superuser:
   ```bash
   python manage.py createsuperuser
   ```
2. Log in as superuser
3. **All actions should work** (no permission restrictions)

---

## The 5 Permissions

| Permission | Codename | Controls |
|------------|----------|----------|
| **Can start / send campaigns** | `can_send_campaigns` | Send emails from campaigns, start campaigns |
| **Can view campaign reports** | `can_view_reports` | View campaign statistics and reports |
| **Can add targets** | `can_manage_targets` | Import CSV, create/edit/delete targets |
| **Can manage email templates** | `can_manage_email_templates` | Create/edit/delete email templates |
| **Can manage landing pages** | `can_manage_landing_pages` | Create/edit/delete landing pages |

---

## Example Permission Scenarios

### Scenario 1: Campaign Operator (Can send campaigns & view reports)

```python
user.user_permissions.add(
    Permission.objects.get(codename='can_send_campaigns'),
    Permission.objects.get(codename='can_view_reports'),
)
```

**Can do:**
- ✅ Send campaign emails
- ✅ View campaign reports
- ❌ Create email templates
- ❌ Import targets
- ❌ Create landing pages

---

### Scenario 2: Content Manager (Can manage templates & landing pages)

```python
user.user_permissions.add(
    Permission.objects.get(codename='can_manage_email_templates'),
    Permission.objects.get(codename='can_manage_landing_pages'),
    Permission.objects.get(codename='can_manage_targets'),
    Permission.objects.get(codename='can_view_reports'),
)
```

**Can do:**
- ✅ Create/edit email templates
- ✅ Create/edit landing pages
- ✅ Import/manage targets
- ✅ View reports
- ❌ Send campaigns

---

### Scenario 3: Full Admin (Superuser - all permissions)

```python
user.is_superuser = True
user.save()
```

**Can do:**
- ✅ Everything (no restrictions)

---

## Checking Permissions Programmatically

### In Admin Classes

```python
class CampaignAdmin(admin.ModelAdmin):
    def send_campaign_emails(self, request, queryset):
        # Permission is automatically checked by has_*_permission methods
        # But you can also manually check:
        if not request.user.has_perm('core.can_send_campaigns'):
            messages.error(request, "You don't have permission")
            return
        
        # ... rest of action
```

### In Views

```python
from django.contrib.auth.decorators import permission_required

@permission_required('core.can_view_reports')
def campaign_report(request, campaign_id):
    # Only users with permission can access this
    ...
```

### In Templates

```html
{% if perms.core.can_send_campaigns %}
    <button>Send Campaign</button>
{% else %}
    <p>You don't have permission to send campaigns</p>
{% endif %}
```

---

## Troubleshooting

### User sees "Permission Denied"

1. **Check user is staff:**
   ```
   /admin/auth/user/ → Edit user → Staff status checkbox
   ```

2. **Check permission is assigned:**
   ```
   /admin/auth/user/ → Edit user → Permissions section
   ```

3. **If superuser, should have all permissions:**
   ```python
   user.is_superuser = True
   user.save()
   ```

4. **Clear browser cache** and refresh

### Permission not showing in admin

```bash
# Ensure migration is applied
python manage.py migrate core

# Restart Django server
python manage.py runserver

# Or check migration status
python manage.py showmigrations core
```

---

## Files Changed

| File | Changes |
|------|---------|
| `core/models.py` | Added Meta permissions to 4 models |
| `core/admin.py` | Added CustomUserAdmin, permission checks |
| `core/views.py` | Added @permission_required decorator |
| `core/migrations/0016_...` | Auto-generated migration |

---

## Next Steps

1. ✅ Run `python manage.py migrate` (if not done)
2. ✅ Create staff users in `/admin/auth/user/`
3. ✅ Assign permissions to users
4. ✅ Test by logging in as different users
5. ✅ Verify actions are restricted based on permissions

---

## More Info

- Full documentation: [`PERMISSIONS_IMPLEMENTATION.md`](./PERMISSIONS_IMPLEMENTATION.md)
- Django permission docs: https://docs.djangoproject.com/en/5.0/topics/auth/default/
