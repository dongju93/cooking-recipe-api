"""Tests for the user API."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import User

CREATE_USER_URL: str = reverse("user:create")


def create_user(**params) -> User:
    """
    Helper to create a User via the manager, bypassing the API.

    Using `create_user()` directly rather than posting to the API keeps test
    setup fast and isolated — it avoids HTTP overhead and ensures that
    pre-existing users exist in the database regardless of view-layer behavior.
    `**params` is forwarded verbatim so callers can pass any combination of
    email, password, and name without the helper growing a long signature.
    """
    return get_user_model().objects.create_user(**params)  # type: ignore[missing-attribute]


class PublicUserApiTests(TestCase):
    """
    Tests for the unauthenticated (public) user API endpoints.

    Uses TestCase (not SimpleTestCase) because each test writes User records to
    the database. TestCase wraps every test in a transaction that rolls back
    automatically after the test, so database state does not leak between tests.

    APIClient is the DRF test client. It extends Django's built-in test Client
    with helpers for JSON serialization (`.post()` sends `Content-Type:
    application/json` automatically when passed a dict) and authentication
    shortcuts like `force_authenticate()` — not used here since these tests
    intentionally exercise the unauthenticated code path.
    """

    def setUp(self) -> None:
        """Initialise a fresh APIClient before each test method."""
        self.client = APIClient()

    def test_create_user_success(self) -> None:
        """
        A valid POST request creates a user and returns 201 with no password.

        Three assertions together verify the full creation contract:
          1. HTTP 201 Created — the view accepted the payload and called save().
          2. `check_password(raw)` returns True — `create_user()` hashed the
             password before storing it; the raw value was never persisted.
          3. `"password"` is absent from `res.data` — the serializer's
             `write_only=True` prevents the hash from appearing in the response.
        """
        payload: dict[str, str] = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user: AbstractBaseUser = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)  # type: ignore[missing-attribute]

    def test_user_with_email_exists_error(self) -> None:
        """
        Posting a duplicate email returns 400 Bad Request.

        `create_user()` pre-seeds the database with an existing account before
        the API call. DRF's UniqueValidator (auto-generated from `unique=True`
        on the EmailField) catches the conflict during serializer validation and
        returns a 400 before the view attempts any database write.
        """
        payload: dict[str, str] = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        create_user(**payload)
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short_error(self) -> None:
        """
        A password shorter than 5 characters returns 400 and creates no user.

        The `min_length=5` constraint lives in `UserSerializer.Meta.extra_kwargs`
        and is enforced during serializer validation — before `create()` is ever
        called. The second assertion confirms that no partial record was written:
        the user must not exist in the database even though the email is new.
        """
        payload: dict[str, str] = {
            "email": "test@example.com",
            "password": "pw",
            "name": "Test User",
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        user_exists: bool = (
            get_user_model().objects.filter(email=payload["email"]).exists()
        )
        self.assertFalse(user_exists)
