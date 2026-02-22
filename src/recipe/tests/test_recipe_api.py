"""Tests for the recipe API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe

from ..serializers import RecipeSerializer

RECIPE_URL: str = reverse("recipe:recipe-list")


def create_recipe(user, **params) -> Recipe:
    """
    Helper to create a Recipe via the ORM, bypassing the API.

    Using `Recipe.objects.create()` directly rather than posting to the API
    keeps test setup fast and isolated — it avoids HTTP overhead and ensures
    that pre-existing recipes exist in the database regardless of view-layer
    behavior.

    `default.update(params)` lets callers override only the fields they care
    about without repeating the full payload. Any key in `params` replaces the
    corresponding default value; omitted keys keep sensible defaults so every
    required model field is always populated.

    `user` is a positional argument rather than part of `**params` because
    every recipe must have an owner — it is a non-nullable FK on the model and
    should never be accidentally omitted in test setup.
    """
    default: dict[str, Decimal | int | str] = {
        "title": "Sample recipe",
        "time_minutes": 5,
        "price": Decimal("5.50"),
        "description": "Sample recipe description.",
        "link": "https://example.com/recipe.pdf",
    }
    default.update(params)

    return Recipe.objects.create(user=user, **default)


class PublicRecipeApiTests(TestCase):
    """
    Tests for the unauthenticated (public) recipe API endpoints.

    Uses TestCase because each test may write Recipe records to the database.
    TestCase wraps every test in a transaction that rolls back automatically
    after the test, so database state does not leak between tests.

    APIClient is used without any authentication setup — the absence of a token
    is what drives the 401 responses these tests assert.
    """

    def setUp(self) -> None:
        """Initialise a fresh APIClient before each test method."""
        self.client = APIClient()

    def test_auth_required(self) -> None:
        """
        GET /api/v1/recipe/recipes without a token returns 401 Unauthorized.

        No `force_authenticate()` or `Authorization` header is set on the
        client, so the request arrives without credentials. `TokenAuthentication`
        returns None (unauthenticated), and `IsAuthenticated` on `RecipeViewSet`
        responds with 401 before `get_queryset()` is ever reached — confirming
        the recipes endpoint is protected and cannot be accessed anonymously.
        """
        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """
    Tests for the authenticated (private) recipe API endpoints.

    Uses TestCase for database access. Each test method gets a fresh,
    pre-authenticated context via `setUp()`, which creates a real User record
    and calls `force_authenticate()` on the APIClient.

    `force_authenticate()` bypasses `TokenAuthentication` entirely — it directly
    sets `request.user` without an HTTP token lookup. This keeps the tests
    focused on view and serializer behaviour rather than on the authentication
    mechanism, which is covered separately by the public tests.
    """

    def setUp(self) -> None:
        """
        Create a user and a pre-authenticated client before each test.

        A fresh user and client are constructed for every test method so that
        one test cannot corrupt state used by another. `force_authenticate()`
        accepts a User instance and attaches it directly to subsequent requests,
        bypassing token validation — appropriate for tests that assume a valid
        authenticated session exists.
        """
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="user@example.com", password="testpass123"
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self) -> None:
        """
        GET /api/v1/recipe/recipes returns 200 with all recipes for the user.

        Two assertions together verify the full list contract:
          1. HTTP 200 OK — the view accepted the authenticated request and
             returned a successful response.
          2. `res.data == serializer.data` — the response payload exactly matches
             the serialized representation of the database rows, confirming that
             the view passes the queryset through RecipeSerializer without omitting
             or transforming any fields.

        The expected queryset uses `order_by("-id")` to match the ordering
        applied by `RecipeViewSet.get_queryset()`, ensuring the assertion is
        sensitive to ordering regressions.
        """
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.all().order_by("-id")
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore[missing-attribute]

    def test_recipe_list_limited_to_user(self) -> None:
        """
        GET /api/v1/recipe/recipes only returns recipes belonging to the authenticated user.

        Two recipes are created — one for `other_user` and one for `self.user`.
        The response is compared against a serializer seeded with only `self.user`'s
        recipe, verifying that `get_queryset()`'s `.filter(user=request.user)` scope
        works correctly and that cross-user data is never exposed.

        Using `RecipeSerializer(recipes, many=True)` as the expected value rather
        than a hand-written dict keeps the assertion independent of field changes in
        the serializer — if a field is added or removed from RecipeSerializer, the
        test still passes as long as the response mirrors the serializer output.
        """
        other_user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="other@example.com", password="testpass123"
        )
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore[missing-attribute]
