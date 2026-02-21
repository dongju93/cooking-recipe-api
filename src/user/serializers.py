"""Serializers for the user API."""

from typing import Any, ClassVar

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework.serializers import (
    CharField,
    EmailField,
    ModelSerializer,
    Serializer,
    ValidationError,
)

from core.models import User


class UserSerializer(ModelSerializer):
    """
    Serializer for creating and representing User objects.

    ModelSerializer auto-generates fields from the model's field definitions,
    removing the need to redeclare types, max_length, etc. that are already
    specified on the model. The inner Meta class is the configuration point
    that controls which model to introspect and which fields to expose.

    `extra_kwargs` overrides per-field options beyond what can be expressed
    in the model definition alone:
      - `write_only=True` on `password` means the field is accepted on input
        (POST body) but never included in the serialized output (response JSON).
        This prevents the hashed password from being leaked to API consumers.
      - `min_length=5` adds a serializer-level validator that runs before
        `create()` is called — a short password is rejected with a 400 response
        before any database write occurs.

    The `# type: ignore[bad-override]` on the inner Meta class suppresses a
    pyrefly/mypy warning: ModelSerializer declares `Meta` without type stubs,
    so re-declaring it as a class attribute triggers a "bad-override" error even
    though this is the canonical DRF pattern.
    """

    class Meta:  # type: ignore[bad-override]
        model: type[AbstractBaseUser] = get_user_model()
        fields: ClassVar[tuple] = ("email", "password", "name")
        extra_kwargs: ClassVar[dict[str, dict[str, bool | int]]] = {
            "password": {"write_only": True, "min_length": 5}
        }

    def create(self, validated_data: dict[str, str]) -> User:
        """
        Create and return a new User with a securely hashed password.

        DRF calls this method from `serializer.save()` when no instance is
        provided (i.e. for creation, not update). `validated_data` contains
        only the fields that passed validation — at this point `email`,
        `password`, and `name` are all guaranteed to be present and clean.

        Delegating to `create_user()` rather than `User(**validated_data).save()`
        is essential: `create_user()` calls `set_password()`, which hashes the
        plain-text value with PBKDF2-SHA256 before writing to the database.
        Calling `User.objects.create(**validated_data)` directly would store the
        raw password string — a critical security vulnerability.
        """
        return get_user_model().objects.create_user(**validated_data)  # type: ignore[missing-attribute]

    def update(self, instance: User, validated_data: dict[str, str]) -> User:
        """
        Update and return an existing User, re-hashing the password if provided.

        DRF calls this method from `serializer.save()` when an instance is passed
        (i.e. for partial or full update, not creation). `validated_data` contains
        only the fields the caller included — with PATCH this may be a subset of
        all writable fields.

        `validated_data.pop("password", None)` removes the raw password before
        forwarding to `super().update()`. If password were left in, the parent
        implementation would call `setattr(instance, "password", raw_value)`,
        writing the plain-text string directly to the database — a critical security
        vulnerability. Popping it first ensures only safe fields are written by the
        default update path.

        Calling `user.set_password(password)` followed by `user.save()` hashes the
        value and persists it — the same contract as `create_user()`. The explicit
        `user.save()` is necessary because `super().update()` has already returned;
        the instance is not in a pending-save state at this point.
        """
        password: str | None = validated_data.pop("password", None)
        user: User = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user


class AuthTokenSerializer(Serializer):
    """
    Serializer for validating email/password login credentials.

    Uses plain Serializer (not ModelSerializer) because this is not a
    model-backed resource — it never reads from or writes to a database
    row directly. Its sole job is to validate incoming credentials and
    attach the authenticated User object to `attrs` for the view to consume.

    `trim_whitespace=False` on the password field is intentional: whitespace
    is valid inside a password, and stripping it silently would cause valid
    credentials to be rejected (e.g. a password that begins or ends with a
    space would be modified before comparison, producing an auth failure).
    """

    email = EmailField()
    password = CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Authenticate the provided credentials and attach the user to attrs.

        DRF calls `validate()` after all individual field validators pass but
        before the serializer returns the cleaned data. It receives the full
        `attrs` dict, making it the correct place for cross-field or
        side-effectful validation like an authentication check.

        `authenticate()` queries the backend configured in AUTHENTICATION_BACKENDS
        (Django's default ModelBackend checks the username/password against the
        database). We pass `username=email` because the custom User model sets
        USERNAME_FIELD = "email". A return value of None means authentication
        failed — the user either does not exist or the password is wrong. We treat
        both cases identically to avoid leaking whether an email is registered.

        Raising ValidationError here causes `is_valid()` to return False, and DRF
        will return a 400 Bad Request. Attaching `user` to `attrs` passes it to the
        view (ObtainAuthToken.post), which reads `serializer.validated_data["user"]`
        to look up or create the auth token.
        """
        email: str = attrs["email"]
        password: str = attrs["password"]

        user: AbstractBaseUser | None = authenticate(
            request=self.context["request"],
            username=email,
            password=password,
        )
        if not user:
            raise ValidationError(
                "Unable to authenticate with provided credentials.",
                code="authentication",
            )

        attrs["user"] = user
        return attrs
