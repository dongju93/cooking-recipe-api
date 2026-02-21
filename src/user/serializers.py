"""Serializers for the user API."""

from typing import ClassVar

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework.serializers import ModelSerializer

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
