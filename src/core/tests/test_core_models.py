"""Tests for the custom User model in core."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Recipe, Tag

if TYPE_CHECKING:
    from ..models import User


def create_user(
    email: str = "user@example.com", password: str = "testpass123"
) -> "User":
    """
    Factory helper that creates and returns a regular User for use in tests.

    Default arguments let individual tests call `create_user()` with no arguments
    when they only need a valid user and don't care about specific credentials.
    Tests that need a distinct user (e.g. to verify isolation between users) can
    override either argument: `create_user(email="other@example.com")`.

    Uses get_user_model() rather than a direct import of core.models.User so that
    this helper stays decoupled from the concrete model path and continues to work
    correctly if AUTH_USER_MODEL is ever changed.
    """
    return get_user_model().objects.create_user(email=email, password=password)  # type: ignore[missing-attribute]


class ModelTests(TestCase):
    """
    Tests for the custom User model.

    Uses TestCase (not SimpleTestCase) because each test needs to write and query
    User records in the database. TestCase wraps each test in a transaction that
    rolls back automatically after the test, keeping the database clean between runs.

    get_user_model() returns the model class set in settings.AUTH_USER_MODEL. Using
    it instead of importing User directly is the recommended pattern — it keeps tests
    decoupled from a specific model path and works correctly with the Django test
    runner's app registry.
    """

    def test_create_user_with_email_successful(self) -> None:
        """
        User is created with the correct email and a hashed password.

        check_password(raw) re-hashes the candidate value using the same algorithm
        and salt stored in user.password, then does a constant-time comparison.
        It returns True only if the raw value matches — confirming that set_password()
        stored a proper hash rather than plain text.
        """
        email: str = "test@example.com"
        password: str = "testpass123"
        user: User = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email=email, password=password
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self) -> None:
        """
        Email domain is normalised to lowercase regardless of input casing.

        BaseUserManager.normalize_email() lowercases only the domain portion
        (after @), leaving the local part unchanged. This prevents the same
        address from creating duplicate accounts (e.g. "user@EXAMPLE.COM" and
        "user@example.com" must resolve to the same account).

        Ten cases cover all-uppercase, mixed-case, and special-character variants
        across different TLDs, including multi-part domains like .co.uk.
        """
        mock_emails: list[list[str]] = [
            ["test1@EXAMPLE.com", "test1@example.com"],
            ["Test2@Example.com", "Test2@example.com"],
            ["TEST3@EXAMPLE.com", "TEST3@example.com"],
            ["test4@example.COM", "test4@example.com"],
            ["User@GMAIL.COM", "User@gmail.com"],
            ["ADMIN@COMPANY.ORG", "ADMIN@company.org"],
            ["Info@Test.Co.Uk", "Info@test.co.uk"],
            ["support+tag@DOMAIN.IO", "support+tag@domain.io"],
            ["John.Doe@EXAMPLE.NET", "John.Doe@example.net"],
            ["TEST_USER@MAIL.COM", "TEST_USER@mail.com"],
        ]
        for email, expected in mock_emails:
            user: User = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
                email=email, password="mock123"
            )
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raise_error(self) -> None:
        """
        Creating a user with an empty email raises ValueError.

        The assertRaises context manager verifies that the body of the `with` block
        raises the specified exception. Because email is the USERNAME_FIELD, an
        empty value must be rejected before reaching the database — the UserManagement
        manager enforces this explicitly at the top of create_user().
        """
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(  # type: ignore[missing-attribute]
                email="", password="test123"
            )

    def test_create_superuser(self) -> None:
        """
        Superuser is created with is_staff and is_superuser both True.

        is_staff=True is required to log in to the Django admin (/admin/).
        is_superuser=True bypasses all individual permission checks in has_perm(),
        granting unrestricted access to every model and action in the admin.
        """
        user = get_user_model().objects.create_superuser(  # type: ignore[missing-attribute]
            email="superuser@example.com", password="superpass123"
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_recipe(self) -> None:
        """
        Recipe is created with all required fields, using Decimal for price accuracy.

        Why Decimal("5.50") instead of float(5.50) or int(550)?

        - Decimal: Exact base-10 arithmetic; 5.50 remains 5.50 (no rounding errors).
                   Maps to PostgreSQL NUMERIC type — guaranteed precision.
                   DRF serializes to string in JSON ("5.50"), preserving full precision.

        - float:    Binary representation causes rounding: 5.50 ≈ 5.500000000000001.
                    Unacceptable for any financial calculation. Never use for prices.

        - int:      Requires manual conversion (550 = $5.50). Error-prone; unclear
                    whether a value is cents or dollars. Use only in extreme cases.

        This test demonstrates the recommended pattern: always use Decimal
        for monetary fields, as enforced by the Recipe model.
        """
        user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="user@example.com", password="testpass123"
        )

        recipe: Recipe = Recipe.objects.create(
            user=user,
            title="Sample recipe",
            time_minutes=5,
            price=Decimal("5.50"),
            description="Sample recipe description.",
        )

        self.assertEqual(str(recipe), recipe.title)

    def test_create_tag(self) -> None:
        """
        Tag is created with a name and owner, and __str__ returns the tag name.

        Verifies two things in one pass:
          1. Tag.objects.create() persists a valid Tag row linked to a user.
          2. str(tag) delegates to __str__ and returns the name field, matching
             the convention established by Recipe.__str__ and used by the admin,
             shell, and logging throughout the project.

        The `create_user()` helper is used here rather than repeating the
        get_user_model() pattern, keeping the test focused on Tag behaviour.
        """
        user: User = create_user()
        tag: Tag = Tag.objects.create(user=user, name="Tag1")

        self.assertEqual(str(tag), tag.name)
