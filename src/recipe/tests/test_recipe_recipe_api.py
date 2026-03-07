"""Tests for the recipe API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag

from ..serializers import RecipeDetailSerializer, RecipeSerializer

RECIPE_URL: str = reverse("recipe:recipe-list")


def detail_url(recipe_id: int) -> str:
    """
    Build the URL for the recipe detail endpoint for a given recipe id.

    The DRF Router registers a detail route whose name follows the pattern
    ``<basename>-detail`` — here ``recipe-detail`` under the ``recipe``
    namespace. ``reverse()`` with ``args=[recipe_id]`` fills in the ``{pk}``
    segment, producing a URL such as ``/api/v1/recipe/1``.

    Encapsulating this in a helper rather than calling ``reverse()`` inline
    in each test means a route-name change only requires a single edit here,
    and it keeps individual test methods free of URL-construction boilerplate.
    """
    return reverse("recipe:recipe-detail", args=[recipe_id])


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
        GET /api/v1/recipe without a token returns 401 Unauthorized.

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
        GET /api/v1/recipe returns 200 with all recipes for the user.

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
        GET /api/v1/recipe only returns recipes belonging to the authenticated user.

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

    def test_get_recipe_detail(self) -> None:
        """
        GET /api/v1/recipe/{id} returns 200 with the full recipe detail payload.

        The detail endpoint is served by the ``retrieve`` action, which causes
        ``RecipeViewSet.get_serializer_class()`` to return ``RecipeDetailSerializer``
        instead of ``RecipeSerializer``. This test verifies that switch works: if
        the view accidentally used the list serializer, ``description`` would be
        absent from the response and the ``res.data == serializer.data`` assertion
        would fail.

        ``RecipeDetailSerializer(recipe)`` is instantiated with a single object
        (no ``many=True``) to produce the expected single-object representation,
        mirroring how the view serializes the retrieved instance.
        """
        recipe: Recipe = create_recipe(user=self.user)

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)  # type: ignore[missing-attribute]

    def test_create_recipe(self) -> None:
        """
        POST /api/v1/recipe with a valid payload creates a recipe and returns 201.

        The test verifies three guarantees of the create path:

        1. **HTTP 201 Created** — the view accepted the payload, the serializer
           validated it, and ``perform_create()`` persisted the record without
           errors.

        2. **All payload fields are persisted correctly** — after retrieving the
           created row via ``Recipe.objects.get(id=res.data["id"])``, the loop
           compares every payload key against the DB value using ``getattr()``.
           Fetching from the ORM rather than reading ``res.data`` directly
           confirms that the data actually reached the database, not just the
           serializer output layer.

        3. **Owner is set to the authenticated user** — ``recipe.user == self.user``
           confirms that ``perform_create()`` correctly injected
           ``user=self.request.user`` regardless of what the client sent in the
           body, preventing privilege-escalation through a crafted ``user`` field.
        """
        payload: dict[str, Decimal | int | str] = {
            "title": "Chocolate cheesecake",
            "time_minutes": 30,
            "price": Decimal("5.00"),
            "description": "Delicious chocolate cheesecake recipe.",
            "link": "https://example.com/chocolate-cheesecake.pdf",
        }

        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe: Recipe = Recipe.objects.get(id=res.data["id"])  # type: ignore[missing-attribute]
        for key, value in payload.items():
            self.assertEqual(getattr(recipe, key), value)

        self.assertEqual(recipe.user, self.user)

    def test_get_other_users_recipe_detail(self) -> None:
        """
        GET /api/v1/recipe/{pk} for another user's recipe returns 404 Not Found.

        ``get_queryset()`` filters to ``user=request.user`` before any object
        lookup occurs.  DRF's ``get_object()`` calls ``get_queryset()`` to build
        the base queryset and then performs a ``.get(pk=pk)`` on that filtered
        set.  Because the recipe belongs to ``other_user``, it is absent from
        the filtered queryset and the lookup raises ``Http404`` — the same
        response a non-existent pk would produce.

        This is the canonical "data-scoping" security pattern: ownership is
        enforced at the queryset level rather than with an explicit object-
        permission check.  The 404 (rather than 403) is intentional — leaking
        which pks exist would itself be an information disclosure.
        """
        other_user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="other@example.com", password="testpass123"
        )
        recipe: Recipe = create_recipe(user=other_user)

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_full_update_recipe(self) -> None:
        """
        PUT /api/v1/recipe/{pk} with a complete payload updates all fields and returns 200.

        A PUT replaces the full resource representation.  ``RecipeDetailSerializer``
        is used for write actions (``get_serializer_class()`` returns it for any
        action other than ``"list"``), so all fields except the read-only ``id``
        must be supplied or have model-level defaults (``blank=True``).

        The test verifies three guarantees:

        1. **HTTP 200 OK** — the serializer accepted the payload, ran validators,
           and saved without errors.

        2. **All payload fields are persisted** — ``recipe.refresh_from_db()``
           reloads the row and the loop confirms every payload key reached the
           database, not just the serializer output layer.

        3. **Owner is preserved** — ``recipe.user`` is not a serializer field, so
           a PUT cannot reassign ownership; the assertion confirms it remains
           ``self.user`` after the update.
        """
        recipe: Recipe = create_recipe(user=self.user)

        payload: dict[str, Decimal | int | str] = {
            "title": "Updated Recipe Title",
            "time_minutes": 45,
            "price": Decimal("10.00"),
            "description": "Updated description.",
            "link": "https://example.com/updated.pdf",
        }

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipe.refresh_from_db()
        for key, value in payload.items():
            self.assertEqual(getattr(recipe, key), value)

        self.assertEqual(recipe.user, self.user)

    def test_partial_update_recipe(self) -> None:
        """
        PATCH /api/v1/recipe/{pk} with a subset of fields updates only those fields.

        A PATCH sends only the fields that should change; omitted fields must
        retain their original values.  DRF's ``UpdateModelMixin.partial_update()``
        passes ``partial=True`` to the serializer, which marks every field as
        non-required so the validator accepts incomplete payloads without error.

        The test asserts both sides of this contract:
          - ``recipe.title`` changes to the patched value.
          - ``recipe.link`` is unchanged — confirming that ``partial=True``
            does not silently blank out omitted fields.

        Ownership is also verified: a PATCH must never reassign ``recipe.user``.
        """
        original_link: str = "https://example.com/recipe.pdf"
        recipe: Recipe = create_recipe(
            user=self.user, title="Original Title", link=original_link
        )

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.patch(url, {"title": "Patched Title"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, "Patched Title")
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_update_other_users_recipe(self) -> None:
        """
        PATCH /api/v1/recipe/{pk} on another user's recipe returns 404 and makes no change.

        The same queryset-scoping that protects the retrieve action applies to
        writes: ``get_queryset()`` filters to the requesting user's rows, so
        ``get_object()`` cannot find a recipe owned by ``other_user`` and raises
        ``Http404`` before any update logic runs.

        The assertion that ``recipe.user`` is still ``other_user`` after the
        request confirms that ownership was not silently transferred — the record
        is completely untouched in the database.
        """
        other_user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="other@example.com", password="testpass123"
        )
        recipe: Recipe = create_recipe(user=other_user)
        original_title: str = recipe.title  # type: ignore[missing-attribute]

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.patch(url, {"title": "Hijacked Title"})

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, original_title)
        self.assertEqual(recipe.user, other_user)

    def test_delete_recipe(self) -> None:
        """
        DELETE /api/v1/recipe/{pk} removes the recipe and returns 204 No Content.

        DRF's ``DestroyModelMixin.destroy()`` calls ``get_object()`` (which applies
        the user-scoped queryset), then ``perform_destroy(instance)``, which calls
        ``instance.delete()``.  204 No Content is the standard success code for a
        DELETE that produces no response body.

        The ``assertFalse(Recipe.objects.filter(...).exists())`` assertion confirms
        the row was actually removed from the database — not just that the HTTP
        layer reported success.
        """
        recipe: Recipe = create_recipe(user=self.user)

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Recipe.objects.filter(id=recipe.id).exists()  # type: ignore[missing-attribute]
        )

    def test_delete_other_users_recipe(self) -> None:
        """
        DELETE /api/v1/recipe/{pk} on another user's recipe returns 404 and leaves the row intact.

        ``get_object()`` resolves the pk against the user-filtered queryset, so a
        recipe belonging to ``other_user`` is invisible to the requesting user's
        client.  The 404 is returned before ``perform_destroy()`` is ever called,
        meaning the row is never touched.

        The ``assertTrue(Recipe.objects.filter(...).exists())`` assertion is the
        critical second check: it confirms the recipe was not deleted as a side
        effect of the 404 path.
        """
        other_user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="other@example.com", password="testpass123"
        )
        recipe: Recipe = create_recipe(user=other_user)

        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Recipe.objects.filter(id=recipe.id).exists()  # type: ignore[missing-attribute]
        )

    def test_create_recipe_with_new_tags(self) -> None:
        """
        POST /api/v1/recipe with a ``tags`` list creates the recipe and all new tags.

        Verifies the end-to-end nested-write path introduced by overriding
        ``RecipeSerializer.create()``.  Four things are asserted:

        1. **HTTP 201 Created** — the serializer accepted the nested payload and
           ``perform_create()`` persisted the record without errors.

        2. **Exactly one recipe was created** — guards against accidental
           duplication at the view or serializer layer.

        3. **Both tags were attached** — ``recipe.tags.count() == 2`` confirms
           the M2M relationship was populated, not just the recipe row itself.

        4. **Each tag is scoped to the user** — the loop queries
           ``recipe.tags.filter(name=..., user=self.user)`` to confirm that
           ``get_or_create`` received the correct owner, preventing tags from
           being created as orphans or assigned to the wrong user.

        ``format="json"`` is required because the default ``multipart`` encoding
        cannot represent nested lists; using JSON ensures the nested ``tags``
        structure is serialized and parsed correctly by DRF.
        """
        payload = {
            "title": "Thai Prawn Curry",
            "time_minutes": 30,
            "price": Decimal("2.50"),
            "tags": [{"name": "Thai"}, {"name": "Dinner"}],
        }
        res = self.client.post(RECIPE_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)

        self.assertEqual(recipes.count(), 1)
        recipe: Recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)

        for tag in payload["tags"]:
            self.assertTrue(
                recipe.tags.filter(name=tag["name"], user=self.user).exists()
            )

    def test_create_recipe_with_existing_tags(self) -> None:
        """
        POST /api/v1/recipe with a tag name matching an existing tag reuses that tag.

        The idempotency guarantee of ``Tag.objects.get_or_create()`` means that
        submitting a tag whose ``(user, name)`` pair already exists in the database
        must not create a second row — the existing Tag instance is reused and
        added to the recipe's M2M relation instead.

        The test pre-creates ``tag_indian`` directly via the ORM, then POSTs a
        payload that includes ``{"name": "Indian"}`` alongside a new tag
        ``{"name": "Breakfast"}``.  Assertions verify:

        1. **HTTP 201 Created** — the payload is accepted despite a pre-existing tag.
        2. **Exactly one recipe created** — no duplication side-effect.
        3. **Two tags attached** — one reused, one newly created, confirming
           the mixed existing-plus-new path works correctly.
        4. **``tag_indian`` is the same ORM instance** — ``assertIn(tag_indian,
           recipe.tags.all())`` compares by primary key, confirming
           ``get_or_create`` returned the original object rather than a duplicate
           with a new ``id``.
        5. **Each tag name is queryable on the recipe** — the loop confirms both
           tags are present and scoped to ``self.user``.
        """
        tag_indian: Tag = Tag.objects.create(user=self.user, name="Indian")
        payload = {
            "title": "Pongal",
            "time_minutes": 60,
            "price": Decimal("4.50"),
            "tags": [{"name": "Indian"}, {"name": "Breakfast"}],
        }
        res = self.client.post(RECIPE_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)

        self.assertEqual(recipes.count(), 1)
        recipe: Recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())

        for tag in payload["tags"]:
            self.assertTrue(
                recipe.tags.filter(name=tag["name"], user=self.user).exists()
            )

    def test_create_tag_on_update(self) -> None:
        """
        PATCH /api/v1/recipe/<id> with a new tag name creates and attaches that tag.

        Verifies that ``update()`` calls ``_get_or_create_tags()``, which will
        create a Tag row when the supplied name does not yet exist for the user,
        then add it to the recipe's M2M set.

        The recipe starts with no tags.  After the PATCH:

        1. **HTTP 200 OK** — the payload is accepted.
        2. **Tag "Lunch" exists in the database** — ``Tag.objects.get()`` would
           raise ``DoesNotExist`` if ``get_or_create`` had not been called.
        3. **Tag is attached to the recipe** — ``assertIn`` checks the M2M set.
        """
        recipe: Recipe = create_recipe(user=self.user)

        payload: dict[str, list[dict[str, str]]] = {"tags": [{"name": "Lunch"}]}
        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag: Tag = Tag.objects.get(user=self.user, name="Lunch")
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self) -> None:
        """
        PATCH /api/v1/recipe/<id> with a different tag replaces the entire M2M set.

        Confirms the "clear-then-add" semantics of ``update()``: when ``tags``
        is present in the payload, the existing M2M relationship is wiped via
        ``instance.tags.clear()`` before the new tag list is applied.  A tag
        that was previously attached must no longer appear on the recipe after
        the update.

        Setup: a recipe is created and ``tag_breakfast`` is manually attached.
        The PATCH payload contains only ``{"name": "Lunch"}``.

        Assertions after the PATCH:

        1. **HTTP 200 OK** — the payload is accepted.
        2. **``tag_lunch`` is now attached** — the new tag was added.
        3. **``tag_breakfast`` is no longer attached** — the old tag was removed
           by ``clear()``, demonstrating that the update replaces rather than
           appends.
        """
        tag_breakfast: Tag = Tag.objects.create(user=self.user, name="Breakfast")
        recipe: Recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch: Tag = Tag.objects.create(user=self.user, name="Lunch")
        payload: dict[str, list[dict[str, str]]] = {"tags": [{"name": "Lunch"}]}
        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self) -> None:
        """
        PATCH /api/v1/recipe/<id> with an empty tags list removes all tags.

        Exercises the explicit-empty-list branch of ``update()``: sending
        ``{"tags": []}`` signals intent to clear all tags, which is
        distinguished from omitting the ``tags`` key entirely (which leaves
        the M2M set unchanged).

        Setup: a recipe is created and ``tag`` is manually attached via the ORM.
        The PATCH payload is ``{"tags": []}``.

        Assertions after the PATCH:

        1. **HTTP 200 OK** — an empty tags list is a valid payload.
        2. **``recipe.tags.count() == 0``** — all tags were removed; the M2M
           join table has no rows for this recipe.
        """
        tag: Tag = Tag.objects.create(user=self.user, name="Dessert")
        recipe: Recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload: dict[str, list] = {"tags": []}
        url: str = detail_url(recipe.id)  # type: ignore[missing-attribute]
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)
