"""Django Admin Configuration Module.

================================================================================
WHAT IS DJANGO ADMIN?
================================================================================

Django Admin is a built-in, production-ready administrative interface that Django
automatically generates for your models. It provides a web-based UI for performing
Create, Read, Update, and Delete (CRUD) operations on database records without
writing custom code.

The admin interface is accessed at /admin/ and is one of Django's most powerful
features, saving developers significant time by eliminating the need to build
custom data management interfaces.

================================================================================
HOW DJANGO ADMIN WORKS
================================================================================

1. AUTOMATIC GENERATION
   ─────────────────────
   - Django automatically creates admin views and forms for any model you register
   - The interface is generated from your model's fields and metadata
   - Minimal code required: just register a model class in admin.py

2. REGISTRATION PROCESS
   ─────────────────────
   Models must be explicitly registered to appear in the admin interface. Two
   registration patterns are supported:

   Pattern A (Decorator - Recommended):
       @admin.register(MyModel)
       class MyModelAdmin(admin.ModelAdmin):
           pass

   Pattern B (Direct registration):
       admin.site.register(MyModel, MyModelAdmin)

3. AUTHENTICATION & AUTHORIZATION
   ───────────────────────────────
   - Only superusers (staff=True, is_superuser=True) can access the admin panel
   - Django uses session-based authentication with username/password login
   - Staff members with specific permissions can perform limited operations
   - Permissions are automatically created for each model (add, change, delete, view)

4. ADMIN OPTIONS (ModelAdmin Attributes)
   ──────────────────────────────────────
   The ModelAdmin class allows customization through attributes:

   - list_display: Fields to show in the list view (e.g., ["id", "name", "email"])
   - list_filter: Fields that enable filtering in the sidebar (e.g., ["created_at"])
   - search_fields: Fields searchable via the search bar (e.g., ["name", "email"])
   - readonly_fields: Fields displayed but not editable (e.g., ["created_at"])
   - fieldsets: Organize form fields into collapsible sections
   - ordering: Default sort order for list view (e.g., ["-created_at"])
   - actions: Custom bulk operations on selected records

5. FORM GENERATION
   ────────────────
   - Django auto-generates forms from model fields
   - Field types automatically determine the appropriate form widgets (e.g.,
     DateTimeField → datetime picker)
   - Validation is inherited from model field definitions
   - Can be customized with a nested Form class or custom ModelForm

6. DATABASE OPERATIONS
   ────────────────────
   - Add: Click "Add" button to create new records via generated form
   - View: Click record to open detail view with all fields
   - Edit: Forms automatically handle updates with validation
   - Delete: Confirmation page protects against accidental deletion
   - Bulk Actions: Perform operations on multiple records simultaneously

7. CHANGE LIST VIEW (List Page)
   ────────────────────────────
   - Displays paginated tables of records
   - Shows columns defined in list_display
   - Includes search, filtering, and sorting
   - Pagination handled automatically
   - Bulk action checkboxes for batch operations

================================================================================
BASIC USAGE EXAMPLE
================================================================================

from django.contrib import admin
from core.models import Recipe, User


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    '''Admin interface for Recipe model with customized behavior.'''
    # Display these fields in the list view
    list_display = ["title", "user", "time_minutes", "price", "created_at"]

    # Add filtering options in the sidebar
    list_filter = ["user", "created_at"]

    # Make title and description searchable
    search_fields = ["title", "description"]

    # Prevent editing of auto-generated timestamp fields
    readonly_fields = ["created_at", "updated_at"]

    # Default sort order (newest first)
    ordering = ["-created_at"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    '''Admin interface for custom User model.'''
    list_display = ["email", "is_staff", "is_superuser", "created_at"]
    list_filter = ["is_staff", "is_superuser"]
    search_fields = ["email"]
    readonly_fields = ["created_at", "updated_at", "password_hash"]

================================================================================
KEY BENEFITS
================================================================================

✓ Zero-Configuration: Register a model and get a full admin interface instantly
✓ Time-Saving: Eliminates writing CRUD views and forms for management tasks
✓ Security: Built-in authentication, authorization, and CSRF protection
✓ Customizable: Extensive options for tailoring the interface without frontend code
✓ Scalable: Handles large datasets with pagination and bulk operations
✓ Production-Ready: Used in millions of Django applications in production
✓ Audit Trail: Can be extended with logging to track changes

================================================================================
SECURITY CONSIDERATIONS
================================================================================

- Access control: Only superusers and staff with permissions can access admin
- Data validation: Django's field validation applies to all admin forms
- CSRF protection: All form submissions are CSRF-protected
- SQL injection: Django ORM prevents SQL injection attacks
- Sensitive data: Use readonly_fields or custom fields to hide passwords, tokens, etc.

================================================================================
WORKFLOW
================================================================================

User visits /admin/
    ↓
Django checks authentication (session/superuser status)
    ↓
If authenticated: Show list of registered models
    ↓
User selects model to manage
    ↓
List view shows all records with filters, search, and sorting
    ↓
User can click "Add" (create), select record (view/edit), or bulk actions
    ↓
Forms auto-generated from model fields with validation
    ↓
Changes saved to database with built-in security protections
    ↓
Confirmation messages show success/failure

================================================================================
"""

from typing import ClassVar

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _lazy

from .models import User


class UserAdmin(BaseUserAdmin):
    """Admin interface customization for the custom User model.

    Extends Django's built-in UserAdmin to work with the custom User model
    that uses email instead of username for authentication. This admin class
    configures:
    - list_display: Fields shown in the user list view
    - fieldsets: Organization of form fields for viewing/editing users
    - readonly_fields: Fields that can be viewed but not modified
    - add_fieldsets: Special form layout when creating new users

    The configuration respects the custom User model's fields:
    - Uses 'email' instead of 'username' as the primary identifier
    - Includes 'name' field for user full names
    - Displays permission flags (is_active, is_staff, is_superuser)
    - Shows last login timestamp as read-only audit information
    """

    ordering: ClassVar[tuple] = ("id",)
    list_display: ClassVar[tuple] = ("email", "name", "is_active", "is_staff")  # type: ignore[bad-override]

    # ╔════════════════════════════════════════════════════════════════════════════╗
    # ║ FIELDSETS - Organizing the Edit User Form                                ║
    # ╚════════════════════════════════════════════════════════════════════════════╝
    # fieldsets: tuple[tuple[str | None, dict[str, Any]], ...]
    #
    # Defines how form fields are organized into collapsible sections when EDITING
    # an existing user. Each fieldset is a tuple: (title, options_dict)
    #
    # Structure:
    #   - title (str | None): Section heading
    #     • None = no heading (default section)
    #     • str = collapsible section with heading (e.g., "Permissions")
    #
    #   - options_dict (dict):
    #     • 'fields': tuple of model field names to include in this section
    #     • 'classes': tuple of CSS classes (e.g., ("collapse",) for collapsible)
    #     • 'description': Optional help text displayed above the section
    #
    # Visual Result:
    #   ┌─ [No heading] ───────────────┐
    #   │ Email: [text field]          │
    #   │ Password: [password field]   │
    #   └──────────────────────────────┘
    #   ┌─ [Permissions] ───────────────┐  ← Collapsible section
    #   │ ☑ Active                      │
    #   │ ☑ Staff                       │
    #   │ ☑ Superuser                   │
    #   └──────────────────────────────┘
    #   ┌─ [Important dates] ───────────┐
    #   │ Last login: [read-only]       │
    #   └──────────────────────────────┘
    fieldsets: ClassVar[tuple] = (
        # Fieldset 1: Credentials (no heading, always shown)
        (None, {"fields": ("email", "password")}),
        # Fieldset 2: Permissions (titled section for privilege management)
        (
            _lazy("Permissions"),  # _lazy() for lazy translation support
            {
                "fields": (
                    "is_active",  # Toggle user account active/inactive
                    "is_staff",  # Controls access to Django admin interface
                    "is_superuser",  # Grants unrestricted admin access
                )
            },
        ),
        # Fieldset 3: Audit trail (read-only timestamps)
        (
            _lazy("Important dates"),
            {"fields": ("last_login",)},  # Single field in tuple (note trailing comma)
        ),
    )

    # Fields marked as read-only: displayed but not editable in admin forms
    # Prevents accidental modification of audit timestamps
    readonly_fields: ClassVar[tuple] = ("last_login",)
    # ╔════════════════════════════════════════════════════════════════════════════╗
    # ║ ADD_FIELDSETS - Organizing the Create User Form                           ║
    # ╚════════════════════════════════════════════════════════════════════════════╝
    # add_fieldsets: tuple[tuple[str | None, dict[str, Any]], ...]
    #
    # Defines form organization when CREATING a new user (different from editing).
    # Same structure as fieldsets, but tailored for user registration workflow.
    #
    # Key Differences from fieldsets:
    #
    # 1. PASSWORD FIELDS
    #    • fieldsets uses:    "password" (single field, shows hashed password)
    #    • add_fieldsets uses: "password1", "password2" (two fields for validation)
    #
    #    Why? When creating a user:
    #    - password1 = Initial password entry (with validation feedback)
    #    - password2 = Confirm password (verified to match password1)
    #    - Prevents typos and ensures user enters intended password
    #
    #    When editing an existing user:
    #    - "password" field is hidden/special to reset the password
    #    - Shows hashed value (not displayed as form input)
    #
    # 2. CSS CLASSES
    #    • "classes": ("wide",) makes the entire form section full-width
    #    • Improves UX for multiline fields or password confirmation
    #
    # 3. TYPICALLY FLATTER STRUCTURE
    #    • add_fieldsets is often one large fieldset with all fields
    #    • fieldsets is split into logical sections (credentials, permissions, audit)
    #
    # Visual Result of add_fieldsets:
    #   ┌───────────────────────────────────────────┐
    #   │ Email: [__________________________]       │  ← Full width form
    #   │ Password: [__________________________]    │
    #   │ Password confirmation: [__________]      │
    #   │ Name: [__________________________]        │
    #   │ ☑ Active    ☑ Staff    ☑ Superuser      │
    #   └───────────────────────────────────────────┘
    add_fieldsets: ClassVar[tuple] = (  # type: ignore[bad-override]
        (
            None,  # No section title (shows all fields in one group)
            {
                "classes": ("wide",),  # CSS class for full-width form display
                "fields": (
                    "email",  # Primary identifier (lowercase normalized email)
                    "password1",  # Initial password (with strength feedback)
                    "password2",  # Confirmation password (matched against password1)
                    "name",  # User's full name
                    "is_active",  # Checkbox: immediately activate account
                    "is_staff",  # Checkbox: grant admin panel access
                    "is_superuser",  # Checkbox: grant unlimited admin permissions
                ),
            },
        ),
    )


admin.site.register(User, UserAdmin)
