"""Custom User model using email as the login identifier instead of username."""

from typing import Any, ClassVar

from django.conf import settings
from django.contrib.auth.base_user import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.contrib.auth.models import PermissionsMixin
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DecimalField,
    EmailField,
    ForeignKey,
    IntegerField,
    Model,
    TextField,
)


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
        user with an unusable password. This is appropriate for users who authenticate
        through external providers (OAuth, SAML, etc.) that manage their own token/
        credential validation. Note: These users never call authenticate(), so the fact
        that authenticate() would reject any password attempt is irrelevant to their
        login flow.

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

    def create_superuser(self, email: str, password: str) -> "User":
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
    # // TODO: Define user model using Pydantic BaseModel to validate input data or use dataclass to define the model and use it in serializer for input validation.
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


class Recipe(Model):
    """
    Represents a cooking recipe owned by a specific user.

    Extends Django's base Model class directly — no auth machinery is
    needed here, unlike User which extends AbstractBaseUser. This gives
    us a plain database-backed model with Django's ORM query interface.

    The ForeignKey to settings.AUTH_USER_MODEL (rather than a direct import
    of the User class) is the recommended Django pattern for two reasons:
      1. It avoids circular imports — core.models defines both User and Recipe,
         but apps outside core that define models referencing the user should
         not couple themselves to core.models.User directly.
      2. It honours AUTH_USER_MODEL at runtime, so if the project ever swaps
         to a different user model the FK resolves to the new model without
         touching Recipe's code.

    on_delete=CASCADE means that deleting a User will automatically delete
    all of that user's Recipe rows. This preserves referential integrity at
    the database level (a foreign key constraint enforces it) and prevents
    orphaned recipe rows that belong to no user.

    String fields use blank=True (not null=True) for optional values:
      - Django convention is to store "no value" as an empty string ''
        rather than NULL for string-based columns (CharField, TextField).
      - Mixing NULL and '' creates two representations of "nothing", which
        complicates queries (you'd need both IS NULL and = '').
      - blank=True tells Django form / serializer validation to accept an
        empty string; the DB column itself remains NOT NULL with default ''.

    DecimalField is used for price instead of FloatField because floats use
    IEEE 754 binary representation, which cannot exactly represent most decimal
    fractions (e.g. 0.1 + 0.2 ≠ 0.3). DecimalField maps to NUMERIC in
    PostgreSQL, which stores and computes exact decimal values — essential for
    monetary amounts to avoid rounding errors in totals or comparisons.
    """

    user: ForeignKey = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=CASCADE,
    )
    title: CharField = CharField(max_length=255)
    description: TextField = TextField(blank=True)
    time_minutes: IntegerField = IntegerField()
    price: DecimalField = DecimalField(max_digits=5, decimal_places=2)
    link: CharField = CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        """Return the recipe title as its human-readable string representation.

        Django's admin changelist, shell introspection, and logging all call
        __str__ when displaying model instances. Returning the title makes
        Recipe objects immediately identifiable without needing to inspect the
        primary key or other fields.
        """
        return self.title
