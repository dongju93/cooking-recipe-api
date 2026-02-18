"""
core/models.py — Custom User Model for email-based authentication.

Django vs FastAPI mental model
──────────────────────────────
In FastAPI you typically separate concerns across three layers:
  - Pydantic BaseModel  → request/response validation & serialization
  - SQLAlchemy Model    → database schema & ORM queries
  - Repository/Service  → business logic / data access

In Django these collapse into ONE class: the Django Model.
  - It *defines* the DB schema (like an SQLAlchemy Table)
  - It *validates* data at the field level (like Pydantic, but lighter)
  - It *IS* the query interface via its Manager (.objects.filter(...))

Django's ORM is "Active Record" style (each instance knows how to save
itself) while SQLAlchemy is "Data Mapper" style (a separate Session
coordinates persistence).
"""

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

    What is a Manager?
    ──────────────────
    In Django, every model has at least one Manager — accessible via the
    class-level `objects` attribute (e.g. User.objects.all()).

    Think of it as a query factory / repository bound to a specific model.
    It is roughly equivalent to a SQLAlchemy session scoped to one table,
    or a FastAPI dependency that wraps your DB session + model together.

    Why subclass BaseUserManager?
    ──────────────────────────────
    BaseUserManager provides two important helpers that plain Manager
    does not ship with:
      - make_password(raw_password)  — hashes a plain-text password
      - normalize_email(email)       — lowercases the domain part

    We inherit from it so our create_user() has access to set_password()
    (which calls make_password internally) without re-implementing hashing.

    Generic parameter BaseUserManager["User"]
    ─────────────────────────────────────────
    This is a PEP 484 forward reference. "User" (as a string) avoids a
    NameError because the User class is defined *after* this class in the
    file. At runtime Django ignores this annotation; mypy/pyrefly use it
    for type inference on self.model and queryset return types.
    """

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        """
        Create, persist, and return a regular (non-superuser) User.

        Parameters
        ----------
        email : str
            The user's email address. Used as the USERNAME_FIELD.
        password : str | None
            Plain-text password. Will be hashed before storage.
            Pass None to create a user with an unusable password
            (e.g. OAuth / SSO users who never set a local password).
        **extra_fields : Any
            Any additional model fields (e.g. name="Alice").

        How self.model works
        ────────────────────
        BaseUserManager sets self.model automatically to the model class
        that declared `objects = UserManagement()`. So `self.model(...)` is
        equivalent to calling `User(...)` — it instantiates an unsaved
        in-memory User object, just like Pydantic's MyModel(...).

        How set_password works (important for security)
        ────────────────────────────────────────────────
        `user.set_password(raw_password)` never stores the plain-text value.
        Internally it calls Django's `make_password()`:
          1. Selects a hasher (PBKDF2-SHA256 by default, configurable via
             PASSWORD_HASHERS in settings.py).
          2. Generates a cryptographically random salt.
          3. Produces a string like:
             "pbkdf2_sha256$720000$<salt>$<hash>"
          4. Stores that string in user.password.

        `check_password(raw, encoded)` later re-hashes the candidate and
        does a constant-time comparison — never comparing plain-text.

        How save(using=self._db) works
        ──────────────────────────────
        `save()` is the Active Record "persist to DB" call — equivalent to:
          session.add(user); session.commit()  # SQLAlchemy
          await user_repo.save(user)           # FastAPI repository pattern

        `using=self._db` routes the INSERT to the correct database alias
        defined in settings.DATABASES. In single-DB projects this is always
        "default", but it matters in multi-tenant or read-replica setups
        where you may have "default" (write) and "replica" (read) aliases.
        """
        user: User = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using email (not username) as the login identifier.

    Why not use Django's built-in User?
    ────────────────────────────────────
    Django ships `django.contrib.auth.models.User` with a `username` field.
    Swapping to email-based auth after your first migration is painful
    (requires data migrations and schema changes). Best practice is to
    define a custom User model at project start — even if you don't need
    customisation yet — so you own the schema from day one.

    Class hierarchy explained
    ─────────────────────────
    AbstractBaseUser  (django.contrib.auth.base_user)
      └─ Provides: password hashing, last_login field, set_password(),
                   check_password(), get_session_auth_hash().
         Does NOT include: username, email, is_staff, groups, permissions.
         You must declare USERNAME_FIELD and REQUIRED_FIELDS yourself.

    PermissionsMixin  (django.contrib.auth.models)
      └─ Provides: is_superuser flag, groups M2M, user_permissions M2M,
                   has_perm(), has_module_perms().
         Plugs into Django's permission framework (used by the admin, DRF
         IsAdminUser, etc.) without coupling us to the default User schema.

    Together they give us: auth + permissions, without the username baggage.

    How Django model fields work (Descriptor Protocol)
    ───────────────────────────────────────────────────
    At class definition time, `EmailField(max_length=255, unique=True)` is
    a Django Field *descriptor* object stored on the class. Django's
    ModelBase metaclass (the __init_subclass__ machinery) inspects these
    descriptors to:
      1. Build the SQL schema for migrations (CREATE TABLE / ALTER TABLE).
      2. Register validators (max_length, unique constraints).
      3. Set up __get__/__set__ so that `instance.email` returns the actual
         value from the instance's __dict__, not the descriptor itself.

    This is fundamentally different from Pydantic where fields are declared
    via `__annotations__` and processed by __class_getitem__ / ModelMetaclass.

    ClassVar annotation clarification
    ──────────────────────────────────
    `email: ClassVar[EmailField]` is a static-analysis hint telling type
    checkers (pyrefly, mypy) "this name at the class level is a ClassVar of
    type EmailField". Without it, type checkers would infer the class
    attribute as EmailField but then get confused when you access
    `user_instance.email` and it returns `str` (the descriptor's __get__
    return type). ClassVar tells them: the descriptor lives on the class;
    don't treat it as an instance attribute of that type.

    At runtime Django ignores ClassVar completely.
    """

    # ──────────────────────────────────────────────────────────────────────
    # Fields
    # Each Field(...) call creates a descriptor + registers schema metadata.
    # Equivalent to a SQLAlchemy Column(...) inside a mapped class.
    # ──────────────────────────────────────────────────────────────────────

    email: ClassVar[EmailField] = EmailField(
        max_length=255,
        unique=True,
        # unique=True → Django adds a UNIQUE INDEX in the migration.
        # EmailField → subclass of CharField that runs EmailValidator before save.
    )

    name: ClassVar[CharField] = CharField(
        max_length=255,
        # No blank=True / null=True → this field is required at the DB level
        # and Django's form/serializer validation will reject empty strings.
    )

    is_active: ClassVar[BooleanField] = BooleanField(  # type: ignore[bad-override]
        default=True,
        # Django convention: deactivated users (is_active=False) cannot log in.
        # authenticate() in django.contrib.auth checks this flag.
        # type: ignore[bad-override] suppresses pyrefly/mypy warning because
        # AbstractBaseUser already declares is_active without a default;
        # our override changes the default, which type checkers flag.
    )

    is_staff: ClassVar[BooleanField] = BooleanField(
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
