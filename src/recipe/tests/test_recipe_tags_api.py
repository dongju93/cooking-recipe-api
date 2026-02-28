"""Tests for the tags API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Tag

from ..serializers import TagSerializer

if TYPE_CHECKING:
    from core.models import User

TAGS_URL: str = reverse("recipe:tag-list")


def create_user(email="user@example.com", password="testpass") -> "User":
    """
    Helper to create a User via the ORM, bypassing the API.

    Accepts keyword-overridable ``email`` and ``password`` arguments so tests that
    need multiple distinct users can call ``create_user(email="other@example.com")``
    without repeating the full payload.  The defaults are intentionally short
    ("testpass") because tag tests have no interest in password complexity rules.

    The ``# type: ignore[missing-argument]`` suppresses a pyrefly error: pyrefly
    resolves ``get_user_model()`` to ``type[AbstractBaseUser]`` whose manager stub
    does not declare ``create_user``; the concrete ``UserManager`` on our custom
    model does, but pyrefly cannot infer that at the callsite.
    """
    return get_user_model().objects.create_user(email=email, password=password)  # type: ignore[missing-argument]


class PublicTagsApiTests(TestCase):
    """
    Tests for the unauthenticated (public) tags API endpoints.

    Uses TestCase because even read-only API tests may rely on database state;
    TestCase wraps every test in a transaction that rolls back automatically after
    the test completes, preventing state leakage between methods.

    APIClient is initialised without any authentication setup — the absence of a
    token is what drives the 401 responses these tests assert.
    """

    def setUp(self) -> None:
        """Initialise a fresh APIClient before each test method."""
        self.client = APIClient()

    def test_auth_required(self) -> None:
        """
        GET /api/v1/recipe/tag without a token returns 401 Unauthorized.

        No ``force_authenticate()`` or ``Authorization`` header is set on the
        client, so the request arrives without credentials.  ``TokenAuthentication``
        returns None (unauthenticated), and ``IsAuthenticated`` on ``TagViewSet``
        short-circuits with 401 before ``get_queryset()`` is ever reached —
        confirming the tags endpoint is protected and cannot be accessed anonymously.
        """
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTagsApiTests(TestCase):
    """
    Tests for the authenticated (private) tags API endpoints.

    Uses TestCase for database access.  Each test method gets a fresh,
    pre-authenticated context via ``setUp()``, which creates a real User record
    and calls ``force_authenticate()`` on the APIClient.

    ``force_authenticate()`` bypasses ``TokenAuthentication`` entirely — it directly
    sets ``request.user`` without an HTTP token lookup.  This keeps the tests
    focused on view and serializer behavior rather than on the authentication
    mechanism, which is covered separately by the public tests.
    """

    def setUp(self) -> None:
        """
        Create a user and a pre-authenticated client before each test.

        A fresh user and client are constructed for every test method so that one
        test cannot corrupt state used by another.  ``force_authenticate()`` accepts
        a User instance and attaches it directly to subsequent requests, bypassing
        token validation — appropriate for tests that assume a valid authenticated
        session exists.
        """
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self) -> None:
        """
        GET /api/v1/recipe/tag returns 200 with all tags for the authenticated user.

        Two assertions together verify the full list contract:

        1. **HTTP 200 OK** — the view accepted the authenticated request and returned
           a successful response.

        2. ``res.data == serializer.data`` — the response payload exactly matches
           the serialized representation of the database rows, confirming that the
           view passes the queryset through ``TagSerializer`` without omitting or
           transforming any fields.

        The expected queryset uses ``order_by("-name")`` to match the ordering
        applied by ``TagViewSet.get_queryset()``, ensuring the assertion is sensitive
        to ordering regressions.
        """
        Tag.objects.create(user=self.user, name="Vegan")
        Tag.objects.create(user=self.user, name="Dessert")

        res = self.client.get(TAGS_URL)

        tags = Tag.objects.all().order_by("-name")
        serializer = TagSerializer(tags, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore [missing-attribute]

    def test_tags_limited_to_user(self) -> None:
        """
        GET /api/v1/recipe/tag only returns tags belonging to the authenticated user.

        Two tags are created — one for ``second_user`` and one for ``self.user``.
        The response is asserted to contain exactly one item, and its ``name`` and
        ``id`` fields are compared against the tag owned by ``self.user``, verifying
        that ``get_queryset()``'s ``.filter(user=request.user)`` scope works correctly
        and that cross-user data is never exposed.

        Checking both ``name`` and ``id`` (rather than a serializer comparison)
        confirms that the single returned item is precisely the expected tag, not an
        accidentally included tag that happens to have the same name.
        """
        second_user: User = create_user(email="second@example.com")
        Tag.objects.create(user=second_user, name="Fruity")
        tag: Tag = Tag.objects.create(user=self.user, name="Comfort Food")

        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)  # type: ignore [missing-attribute]
        self.assertEqual(res.data[0]["name"], tag.name)  # type: ignore [missing-attribute]
        self.assertEqual(res.data[0]["id"], tag.id)  # type: ignore [missing-attribute]
