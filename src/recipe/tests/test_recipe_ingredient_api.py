"""Tests for the ingredients API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from core.models import Ingredient

from ..serializers import IngredientSerializer

if TYPE_CHECKING:
    from core.models import User
INGREDIENT_URL: str = reverse("recipe:ingredient-list")


def detail_url(ingredient_id: int) -> str:
    """
    Build the detail URL for a single ingredient resource.

    Wraps ``reverse("recipe:ingredient-detail", args=[ingredient_id])`` so that
    tests do not embed raw URL strings.  Using ``reverse()`` means the URL is
    derived from the URLconf at test runtime, so renaming a path in ``urls.py``
    is caught immediately rather than silently producing 404s that mask the real
    failure.
    """
    return reverse("recipe:ingredient-detail", args=[ingredient_id])


def create_user(email="user@example.com", password="testpass") -> "User":
    """
    Helper to create a User via the ORM, bypassing the API.

    Accepts keyword-overridable ``email`` and ``password`` arguments so tests that
    need multiple distinct users can call ``create_user(email="other@example.com")``
    without repeating the full payload.  The defaults are intentionally short
    ("testpass") because ingredient tests have no interest in password complexity rules.

    The ``# type: ignore[missing-argument]`` suppresses a pyrefly error: pyrefly
    resolves ``get_user_model()`` to ``type[AbstractBaseUser]`` whose manager stub
    does not declare ``create_user``; the concrete ``UserManager`` on our custom
    model does, but pyrefly cannot infer that at the callsite.
    """
    return get_user_model().objects.create_user(email=email, password=password)  # type: ignore[missing-argument]


class PublicIngredientsApiTests(TestCase):
    """
    Tests for the unauthenticated (public) ingredients API endpoints.

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
        GET /api/v1/recipe/ingredients without a token returns 401 Unauthorized.

        No ``force_authenticate()`` or ``Authorization`` header is set on the
        client, so the request arrives without credentials.  ``TokenAuthentication``
        returns None (unauthenticated), and ``IsAuthenticated`` on
        ``IngredientViewSet`` short-circuits with 401 before ``get_queryset()`` is
        ever reached — confirming the ingredients endpoint is protected and cannot
        be accessed anonymously.
        """
        res: Response = cast(Response, self.client.get(INGREDIENT_URL))

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTests(TestCase):
    """
    Tests for the authenticated (private) ingredients API endpoints.

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
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self) -> None:
        """
        GET /api/v1/recipe/ingredients returns 200 with all ingredients for the authenticated user.

        Two assertions together verify the full list contract:

        1. **HTTP 200 OK** — the view accepted the authenticated request and returned
           a successful response.

        2. ``res.data == serializer.data`` — the response payload exactly matches
           the serialized representation of the database rows, confirming that the
           view passes the queryset through ``IngredientSerializer`` without omitting
           or transforming any fields.

        The expected queryset uses ``order_by("-name")`` to match the ordering
        applied by ``IngredientViewSet.get_queryset()``, ensuring the assertion is
        sensitive to ordering regressions.
        """
        Ingredient.objects.create(user=self.user, name="Kale")

        Ingredient.objects.create(user=self.user, name="Vanilla")

        res: Response = cast(Response, self.client.get(INGREDIENT_URL))

        ingredients: QuerySet[Ingredient] = Ingredient.objects.all().order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_ingredients_limited_to_user(self) -> None:
        """
        GET /api/v1/recipe/ingredients only returns ingredients belonging to the authenticated user.

        Two ingredients are created — one for ``user_2`` and one for ``self.user``.
        The response is asserted to contain exactly one item, and its ``name`` and
        ``id`` fields are compared against the ingredient owned by ``self.user``,
        verifying that ``get_queryset()``'s ``.filter(user=request.user)`` scope
        works correctly and that cross-user data is never exposed.

        Checking both ``name`` and ``id`` (rather than a serializer comparison)
        confirms that the single returned item is precisely the expected ingredient,
        not an accidentally included ingredient that happens to share the same name.
        """
        user_2: User = create_user(email="user_2@example.com")
        Ingredient.objects.create(user=user_2, name="Salt")
        ingredient: Ingredient = Ingredient.objects.create(
            user=self.user, name="Pepper"
        )

        res: Response = cast(Response, self.client.get(INGREDIENT_URL))

        data: list[Any] = cast(list[Any], res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], ingredient.name)
        self.assertEqual(data[0]["id"], ingredient.id)

    def test_update_ingredient(self) -> None:
        """
        PATCH /api/v1/recipe/ingredients/<id> updates the ingredient's name and returns 200.

        An ingredient is created directly via the ORM and then partially updated
        through the API using ``PATCH`` (``partial_update``).  The test asserts
        two things:

        1. **HTTP 200 OK** — ``UpdateModelMixin`` accepted the authenticated
           request and returned a success status.

        2. ``ingredient.name == payload["name"]`` — after calling
           ``refresh_from_db()``, the database row reflects the new value,
           confirming the serializer validated the payload and ``save()`` was
           called.  Relying on ``refresh_from_db()`` rather than re-querying
           the ORM directly guards against Django's object-level caching
           returning a stale in-memory value.
        """
        ingredient: Ingredient = Ingredient.objects.create(
            user=self.user, name="Cilantro"
        )

        payload: dict[str, str] = {"name": "Coriander"}
        url: str = detail_url(ingredient.id)
        res: Response = cast(Response, self.client.patch(url, payload))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.name, payload["name"])

    def test_delete_ingredient(self) -> None:
        """
        DELETE /api/v1/recipe/ingredients/<id> removes the ingredient and returns 204 No Content.

        ``DestroyModelMixin.destroy()`` calls ``get_object()`` (which applies the
        user-scoped queryset from ``get_queryset()``), then ``perform_destroy()``,
        which calls ``instance.delete()``.  204 No Content is the standard success
        code for a DELETE that produces no response body.

        The ``assertFalse(ingredients.exists())`` assertion confirms the row was
        actually removed from the database — not just that the HTTP layer reported
        success.  Filtering by ``user=self.user`` also verifies the delete was
        scoped to the correct owner and did not inadvertently wipe unrelated rows.
        """
        ingredient: Ingredient = Ingredient.objects.create(
            user=self.user, name="Lettuce"
        )

        url: str = detail_url(ingredient.id)
        res: Response = cast(Response, self.client.delete(url))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        ingredients = Ingredient.objects.filter(user=self.user)
        self.assertFalse(ingredients.exists())
