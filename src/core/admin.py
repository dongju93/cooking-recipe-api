"""
Admin configuration for the core app's User model.

Django's admin site (/admin/) auto-generates CRUD views for any model you
register. Models must be explicitly registered here to appear in the admin.
"""

from typing import ClassVar

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _lazy

from .models import Ingredient, Recipe, Tag, User


class UserAdmin(BaseUserAdmin):
    """
    Extends Django's built-in UserAdmin to support email-based authentication.

    BaseUserAdmin (imported as UserAdmin from django.contrib.auth.admin) provides
    a complete admin interface for auth models, including password change links and
    permission widgets. We extend it rather than plain ModelAdmin so those features
    work correctly with our custom User model.

    Key attributes:
      ordering      — default column sort for the changelist (list view).
      list_display  — column names shown in the changelist.
      fieldsets     — layout of the edit-user form. Each entry is a tuple of
                      (title, {"fields": (...)}). title=None means no section
                      heading. "password" here is the hashed-value read-only field
                      provided by BaseUserAdmin, not a plain text input.
      readonly_fields — shown in the form but not editable.
      add_fieldsets — layout of the create-user form. Uses "password1" and
                      "password2" (two separate inputs for confirmation) instead of
                      the single "password" field used when editing an existing user.

    _lazy() (gettext_lazy) marks section title strings for lazy translation —
    the string is only evaluated when rendered, not at import time, which is
    required for Django's i18n system to work correctly.
    """

    ordering: ClassVar[tuple] = ("id",)  # type: ignore[bad-override]
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
    fieldsets: ClassVar[tuple] = (  # type: ignore[bad-override]
        # Fieldset 1: Credentials (no heading, always shown)
        (None, {"fields": ("email", "password", "name")}),
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
    readonly_fields: ClassVar[tuple] = ("last_login",)  # type: ignore[bad-override]
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
admin.site.register(Recipe)
admin.site.register(Tag)
admin.site.register(Ingredient)
