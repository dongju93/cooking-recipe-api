"""Tests for the user API."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import User

CREATE_USER_URL: str = reverse("user:create")
TOKEN_URL: str = reverse("user:token")


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

    def test_create_token_for_user(self) -> None:
        """
        Valid credentials return 200 with a token key in the response body.

        The user is created directly via `create_user()` rather than through the
        API so that test setup is independent of the create-user endpoint. This
        keeps the token test focused on one responsibility: verifying that correct
        credentials produce a token, not that user creation also works.

        Asserting that `"token"` is present in `res.data` rather than checking its
        exact value is sufficient — the token string is opaque to callers; only its
        presence matters for a successful login.
        """
        user_details: dict[str, str] = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        create_user(**user_details)

        payload: dict[str, str] = {
            "email": user_details["email"],
            "password": user_details["password"],
        }
        res = self.client.post(TOKEN_URL, payload)

        self.assertIn("token", res.data)  # type: ignore[missing-attribute]
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_create_token_bad_credentials(self) -> None:
        """
        Wrong password returns 400 Bad Request with no token in the response.

        `authenticate()` inside AuthTokenSerializer.validate() returns None when
        the password does not match, causing a ValidationError to be raised. DRF
        converts this into a 400 response, and no token is generated or returned.

        Asserting `"token" not in res.data` alongside the status code prevents a
        regression where a future change might return 400 but still accidentally
        leak a token value in the error payload.
        """
        create_user(email="test@example.com", password="testpass123", name="Test User")

        payload: dict[str, str] = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }
        res = self.client.post(TOKEN_URL, payload)

        self.assertNotIn("token", res.data)  # type: ignore[missing-attribute]
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_token_blank_password(self) -> None:
        """
        Blank password string returns 400 Bad Request with no token in the response.

        This tests a distinct failure mode from wrong credentials: an empty string
        passes CharField's blank check by default, but `authenticate()` will still
        return None because no stored password hash can match an empty value.

        `trim_whitespace=False` on the password field means the blank value is
        forwarded to authenticate() unchanged — there is no silent stripping that
        could mask what the caller actually sent.
        """
        create_user(email="test@example.com", password="testpass123", name="Test User")

        payload: dict[str, str] = {
            "email": "test@example.com",
            "password": "",
        }
        res = self.client.post(TOKEN_URL, payload)

        self.assertNotIn("token", res.data)  # type: ignore[missing-attribute]
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
