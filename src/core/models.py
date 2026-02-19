"""Custom User model using email as the login identifier instead of username."""

from typing import Any, ClassVar

from django.contrib.auth.base_user import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.contrib.auth.models import PermissionsMixin
from django.db.models import BooleanField, CharField, EmailField


class UserManagement(BaseUserManager["User"]):
    """
    Custom Manager for the User model.

    In Django, every model has at least one Manager accessible as the class-level
    `objects` attribute (e.g. User.objects.all()). The Manager is the query
    interface — it returns QuerySets and provides factory methods like create_user().

    We extend BaseUserManager instead of plain Manager because it adds two helpers:
      - normalize_email(email): lowercases the domain portion of the address
        (e.g. "User@EXAMPLE.COM" → "User@example.com") to prevent duplicate
        accounts caused by case variations.
      - Exposes set_password() / make_password() for safe password hashing.

    The generic string "User" in BaseUserManager["User"] is a PEP 484 forward
    reference to avoid a NameError — the User class is defined after this one in
    the file. Django ignores it at runtime; type checkers use it to infer the
    correct return type for self.model and queryset methods.
    """

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        """
        Create and return a regular (non-superuser) User.

        self.model is set automatically by Django to the model class that declared
        `objects = UserManagement()`, so self.model(...) instantiates an unsaved User.

        set_password(password) hashes the plain-text value with PBKDF2-SHA256 and a
        random salt — the raw password is never stored. Pass password=None to create a
        user with an unusable password (authenticate() will always reject it), which
        is appropriate for OAuth/SSO accounts that have no local password.

        save(using=self._db) writes the record to the database. The `using` argument
        routes the INSERT to the correct database alias in settings.DATABASES — always
        "default" in single-DB projects, but necessary in multi-DB setups where you
        may have separate write and read-replica aliases.
        """
        if not email:
            raise ValueError("Users must have an email address")
        user: User = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email: str, password: str) -> User:
        """
        Create and return a superuser with is_staff=True and is_superuser=True.

        Delegates to create_user() to reuse email validation and password hashing.
        After that save(), is_staff and is_superuser are set in memory and save()
        is called a second time — Django's ORM does not track which fields changed
        between saves, so each save() is an explicit UPDATE of the full current state.

        is_staff=True grants access to Django's /admin/ interface.
        is_superuser=True bypasses all permission checks in has_perm() entirely.

        Called internally by the `createsuperuser` management command.
        """
        user: User = self.create_user(email=email, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model with email-based authentication.

    AbstractBaseUser provides the minimum auth machinery: password hashing,
    the last_login field, and set_password() / check_password(). It intentionally
    omits fields like username — you define USERNAME_FIELD and REQUIRED_FIELDS
    yourself to control which fields are used for authentication.

    PermissionsMixin adds the permission framework: the is_superuser flag, groups
    and user_permissions M2M relations, and has_perm() / has_module_perms() which
    are used by the admin and DRF's IsAdminUser permission class.

    USERNAME_FIELD = "email" tells django.contrib.auth.authenticate() which field
    to look up when a login attempt is made. The field must have unique=True.

    Defining a custom User model at project start is best practice. Django's auth
    system hard-wires the User model into many migrations; swapping it after the
    first migration requires rewriting those migration dependencies manually.

    Fields are annotated as `email: EmailField = EmailField(...)` rather than
    `ClassVar[EmailField]`. django-stubs ships overloaded __get__ / __set__ on each
    Field subclass so that `user.email` is inferred as str. Using ClassVar would
    tell the type checker the field only exists on the class, suppressing that.
    """

    # ──────────────────────────────────────────────────────────────────────
    # Fields
    # Each Field(...) call creates a descriptor + registers schema metadata.
    # Equivalent to a SQLAlchemy Column(...) inside a mapped class.
    # ──────────────────────────────────────────────────────────────────────

    email: EmailField = EmailField(
        max_length=255,
        unique=True,
        # unique=True → Django adds a UNIQUE INDEX in the migration.
        # EmailField → subclass of CharField that runs EmailValidator before save.
    )

    name: CharField = CharField(
        max_length=255,
        # No blank=True / null=True → this field is required at the DB level
        # and Django's form/serializer validation will reject empty strings.
    )

    is_active: BooleanField = BooleanField(  # type: ignore[bad-override]
        default=True,
        # Django convention: deactivated users (is_active=False) cannot log in.
        # authenticate() in django.contrib.auth checks this flag.
        # type: ignore[bad-override] suppresses pyrefly/mypy warning because
        # AbstractBaseUser already declares is_active without a default;
        # our override changes the default, which type checkers flag.
    )

    is_staff: BooleanField = BooleanField(
        default=False,
        # Django admin checks `user.is_staff` to grant access to /admin/.
        # PermissionsMixin checks `user.is_superuser` for full permissions.
        # is_staff=True + specific permissions → limited admin access.
        # is_superuser=True → bypasses all permission checks entirely.
    )

    # ──────────────────────────────────────────────────────────────────────
    # Manager
    # ──────────────────────────────────────────────────────────────────────

    objects: ClassVar[UserManagement] = UserManagement()
    # `objects` is the conventional name for the default Manager.
    # ClassVar[UserManagement] tells the type checker the *concrete* manager
    # type, so User.objects.create_user(...) resolves correctly instead of
    # falling back to the base Manager which has no create_user method.
    # This is what powers User.objects.create_user(...),
    # User.objects.filter(email=...), etc.
    #
    # Django attaches the Manager to the class via a Descriptor as well —
    # accessing User.objects returns the manager; accessing instance.objects
    # raises AttributeError (managers are class-level, not instance-level).

    # ──────────────────────────────────────────────────────────────────────
    # Authentication configuration
    # ──────────────────────────────────────────────────────────────────────

    USERNAME_FIELD = "email"
    # Tells Django's authenticate() which field to use as the "username".
    # django.contrib.auth.authenticate(request, email=..., password=...)
    # will look up User.objects.get(email=<value>) internally.
    #
    # The field named here MUST have unique=True (enforced at system check).
    #
    # REQUIRED_FIELDS is intentionally omitted here. It defaults to [].
    # It only matters for the `createsuperuser` management command — it
    # specifies which extra fields to prompt for interactively. Since we
    # have sensible defaults on all other fields, we leave it empty.
