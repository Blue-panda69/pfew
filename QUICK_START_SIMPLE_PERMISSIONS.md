# Quick Start - Simple Permission System

## What Was Replaced?

The complex Django permission framework has been replaced with a simple **UserProfile model** containing 6 boolean permission flags.

## The 6 Permissions

When you edit a user in the admin, you'll see a "User Profile" section with these checkboxes:

✅ **Can manage users** - Add/edit/delete other admin users  
✅ **Can manage targets** - Add/edit/delete targets & import CSV  
✅ **Can manage email templates** - Add/edit/delete email templates  
✅ **Can manage landing pages** - Add/edit/delete landing pages  
✅ **Can manage campaigns** - Create/edit campaigns & send emails  
✅ **Can view reports** - View campaign reports (read-only)  

## How to Give a User Permission

1. Go to **Django Admin** → **Users**
2. Click on the user you want to edit
3. Scroll down to **"User Profile"**
4. Check the boxes for permissions they need
5. Click **Save**

**Example:** Give "john_smith" permission to view reports:
- Edit john_smith
- In User Profile section, check "Can view reports"
- Save

## What Gets Restricted?

| Feature | Protected By | Where |
|---------|-------------|-------|
| Create/edit/delete users | Can manage users | `/admin/auth/user/` |
| Create/edit/delete targets | Can manage targets | `/admin/core/target/` |
| Import CSV targets | Can manage targets | Target admin CSV import button |
| Add targets to campaign | Can manage targets | Target admin bulk action |
| Create/edit/delete templates | Can manage email templates | `/admin/core/emailtemplate/` |
| Create/edit/delete landing pages | Can manage landing pages | `/admin/core/landingpage/` |
| Create/edit campaigns | Can manage campaigns | `/admin/core/campaign/` |
| Send campaign emails | Can manage campaigns | Campaign admin "Send emails" action |
| View reports | Can view reports | `/admin/campaign-report/` |

## Key Rules

✅ **Superusers** - Always have full access (no need to configure)  
✅ **Staff requirement** - Must be staff member (`is_staff=True`) to see admin at all  
✅ **Auto-creation** - New users automatically get a profile (all unchecked)  
✅ **Existing users** - Already have profiles created  

## Common Scenarios

### Create an Admin Who Can Only View Reports

1. Create user with `is_staff=True`
2. Edit their profile
3. Check ONLY "Can view reports"
4. Save

Result: User sees admin home but can only access the Reports page

### Create a Campaign Manager

1. Create user with `is_staff=True`
2. Edit their profile
3. Check these boxes:
   - Can manage campaigns
   - Can view reports
4. Save

Result: User can manage campaigns, send emails, and view reports

### Create a Full Admin (Non-Superuser)

1. Create user with `is_staff=True`
2. Edit their profile
3. Check ALL 6 boxes
4. Save

Result: User has full admin access (like superuser for these features)

## Testing

### Quick Test

```bash
# Create a test user with limited permissions
python manage.py shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.create_user('testadmin', 'test@example.com', 'password123')
>>> u.is_staff = True
>>> u.save()
>>> u.profile.can_view_reports = True
>>> u.profile.save()
```

Then:
1. Log out
2. Log in as `testadmin`
3. Only "Campaigns" section shows (for viewing reports)
4. Try to add a target → "Permission denied"

## Troubleshooting

**"User cannot see admin section they should have access to"**
- Check user has `is_staff=True`
- Check the permission box is checked in their profile
- Clear browser cache (Ctrl+Shift+Del)

**"User profile missing"**
- Run: `python manage.py create_user_profiles`
- This creates profiles for any user that doesn't have one

**"User can see everything despite no permissions checked"**
- Check if they're a superuser (`is_superuser=True`)
- Superusers always have full access

## Migration Already Applied

✅ Migration `0017_...` has already been applied  
✅ UserProfiles created for existing users  
✅ System check passed  
✅ Ready to use!

## Files to Know About

- `core/models.py` - UserProfile model definition
- `core/admin.py` - Admin customizations with permission checks
- `core/management/commands/create_user_profiles.py` - Bulk profile creation
- `SIMPLE_PERMISSIONS_GUIDE.md` - Complete documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical details

---

**Need help?** Check SIMPLE_PERMISSIONS_GUIDE.md for detailed documentation
