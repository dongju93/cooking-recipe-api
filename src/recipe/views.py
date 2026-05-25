"""Views for the recipe API."""

from typing import Any, Sequence

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from core.models import Ingredient, Recipe, Tag

from .serializers import (
    IngredientSerializer,
    RecipeDetailSerializer,
    RecipeImageSerializer,
    RecipeSerializer,
    TagSerializer,
)


class RecipeViewSet(ModelViewSet):
    """
    ViewSet for managing the authenticated user's recipes.

    ModelViewSet composes all six standard actions — list, create, retrieve,
    update, partial_update, and destroy — from a set of mixins layered on top
    of GenericAPIView. Registering this ViewSet with a DRF Router auto-generates
    two URL patterns: a collection route (/recipes) for list and create, and a
    detail route (/recipes/{pk}) for retrieve, update, partial_update, and destroy.

    `authentication_classes = [TokenAuthentication]` requires an
    `Authorization: Token <key>` header on every request. DRF validates the key
    against the authtoken table and attaches the resolved User to request.user
    before any view logic runs.

    `permission_classes = [IsAuthenticated]` short-circuits with 401 Unauthorized
    if the token is absent or invalid, ensuring unauthenticated callers never reach
    the view body.

    `get_queryset()` is overridden to scope every action to the authenticated user,
    preventing any user from listing, retrieving, or mutating another user's recipes.
    """

    queryset = Recipe.objects.all()
    authentication_classes: Sequence[type[BaseAuthentication]] = [TokenAuthentication]
    permission_classes = [
        IsAuthenticated
    ]  # cannot import private type alias, type hint is 'Sequence[_PermissionClass]'

    def get_queryset(self):  # type: ignore[bad-override]
        """
        Return only the recipes owned by the currently authenticated user.

        ModelViewSet's default implementation returns the full class-level
        `queryset`. Overriding here applies `.filter(user=request.user)` so
        that list, retrieve, update, and destroy are all scoped to the requesting
        user's own data — a caller cannot supply another user's pk and access
        their recipe.

        `order_by("-id")` provides a stable descending insertion-order sort.
        Using the primary key rather than a timestamp avoids ambiguity when multiple
        records share the same created_at value (e.g. in bulk imports or tests), and
        the existing index on id makes the sort cost-free.

        `# type: ignore[bad-override]` suppresses a pyrefly error: the parent class
        declares `get_queryset() -> QuerySet[T_co]` with a bound type variable that
        pyrefly cannot match against our concrete return type when the method
        signature omits an explicit annotation.
        """
        return self.queryset.filter(user=self.request.user).order_by("-id")

    def get_serializer_class(
        self,
    ) -> (
        type[RecipeDetailSerializer]
        | type[RecipeSerializer]
        | type[RecipeImageSerializer]
    ):
        """
        Return the serializer class appropriate for the current router action.

        DRF calls this method (instead of reading `serializer_class` directly)
        when it needs to instantiate a serializer, making it the correct hook
        for per-action serializer switching. `self.action` is set by the router
        before the view method executes and maps to the logical operation name:
        ``"list"``, ``"retrieve"``, ``"create"``, ``"update"``, ``"partial_update"``,
        or ``"destroy"``.

        ``RecipeSerializer`` is returned for ``"list"`` because list responses
        contain many rows and the ``description`` TextField is omitted to keep
        payload size small.

        All other actions (``"retrieve"``, writes) receive ``RecipeDetailSerializer``
        so that the full field set — including ``description`` — is available.
        Writes also benefit from this: a ``create`` or ``update`` caller can supply
        ``description`` and have it validated and saved by the same serializer
        that the ``retrieve`` action uses to read it back.
        """
        if self.action == "list":
            return RecipeSerializer
        elif self.action == "upload_image":
            return RecipeImageSerializer

        return RecipeDetailSerializer

    def perform_create(self, serializer: BaseSerializer) -> None:
        """
        Inject the authenticated user into the recipe before saving.

        DRF calls ``perform_create()`` inside ``CreateModelMixin.create()``
        after ``serializer.is_valid()`` succeeds but before ``serializer.save()``.
        It is the designated hook for attaching server-side context that must
        not be accepted from the client payload — here, the owning user.

        Passing ``user=self.request.user`` as a keyword argument to
        ``serializer.save()`` is equivalent to setting it as a validated field:
        DRF merges it with ``serializer.validated_data`` before calling
        ``Recipe.objects.create()``. Because ``user`` is not listed in
        ``RecipeDetailSerializer.fields``, clients cannot override it — they
        cannot assign their recipe to another user by supplying a ``user`` key
        in the POST body.
        """
        serializer.save(user=self.request.user)

    @action(methods=["POST"], detail=True, url_path="upload-image")
    def upload_image(self, request: Request, pk: int) -> Response:
        """
        Accept and persist an image file upload for the given recipe.

        The ``@action`` decorator registers this method as a non-standard DRF
        route alongside the default ModelViewSet actions.  ``detail=True``
        signals that the route operates on a single instance rather than the
        collection — the router generates the URL
        ``/recipes/{pk}/upload-image/`` (``url_path="upload-image"``).
        ``methods=["POST"]`` restricts the route to POST only; other HTTP
        verbs return 405 Method Not Allowed.

        ``self.get_object()`` retrieves the ``Recipe`` identified by ``pk``,
        applying the user-scoped queryset from ``get_queryset()`` as an implicit
        ownership check — a caller cannot upload to another user's recipe even
        if they know the pk.

        ``self.get_serializer()`` resolves to ``RecipeImageSerializer`` because
        ``get_serializer_class()`` returns it when
        ``self.action == "upload_image"``.  Passing ``data=request.data``
        populates the serializer with the multipart payload containing the
        uploaded file.

        On validation success the serializer saves the file and returns the
        updated ``id`` + ``image`` representation with HTTP 200.  On failure
        the validation errors are returned with HTTP 400 without touching the
        existing image.

        ``pk`` is declared in the signature because DRF's router injects URL
        captures as keyword arguments; the actual record lookup is handled
        internally by ``self.get_object()`` via ``self.kwargs["pk"]``.
        """
        recipe = self.get_object()
        serializer: BaseSerializer = self.get_serializer(recipe, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BaseRecipeAttributeViewSet(
    DestroyModelMixin, UpdateModelMixin, ListModelMixin, GenericViewSet
):
    """
    Shared ViewSet for authenticated, user-scoped recipe attributes.

    Tags and ingredients expose the same three operations: ``list``, ``update`` /
    ``partial_update``, and ``destroy``.  They also share the same access rules:
    token authentication, ``IsAuthenticated`` permission checks, and a queryset
    constrained to the requesting user's rows ordered by descending name.

    Concrete subclasses provide the model-backed ``queryset`` and
    ``serializer_class`` for their specific resource.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    queryset: QuerySet[Any]

    def get_queryset(self):  # type: ignore[bad-override]
        """
        Return only the current user's resources ordered by descending name.

        Subclasses intentionally declare a broad class-level ``queryset`` covering
        all rows for the underlying model.  Scoping is applied here so every list,
        update, and delete action automatically uses the authenticated user's data
        and cannot leak or mutate another user's records.

        ``order_by("-name")`` sorts resources in reverse alphabetical order,
        providing a semantically meaningful, stable sort for list endpoints where
        alphabetical grouping is more useful than insertion order.

        ``# type: ignore[bad-override]`` suppresses the same pyrefly false positive
        as in ``RecipeViewSet``: the parent's generic return type cannot be matched
        against the concrete return type when the method omits an explicit annotation.
        """
        return self.queryset.filter(user=self.request.user).order_by("-name")


class TagViewSet(BaseRecipeAttributeViewSet):
    """
    ViewSet for managing the authenticated user's tags.

    Extends ``BaseRecipeAttributeViewSet`` to inherit token authentication,
    ``IsAuthenticated`` permission enforcement, and user-scoped queryset
    filtering without repetition.  The three exposed actions — ``list``,
    ``update`` / ``partial_update``, and ``destroy`` — cover the tag management
    surface: ``create`` and ``retrieve`` are intentionally absent because tags
    are created implicitly when a recipe references them by name via
    ``RecipeSerializer._get_or_create_tags()``.

    ``serializer_class = TagSerializer`` wires all actions to the minimal
    ``id`` + ``name`` representation.  The ``# type: ignore[bad-override]``
    silences the pyrefly false positive triggered by narrowing the parent's
    ``type[BaseSerializer]`` annotation to the concrete ``type[TagSerializer]``.
    """

    serializer_class: type[TagSerializer] = TagSerializer  # type: ignore[bad-override]
    queryset = Tag.objects.all()


class IngredientViewSet(BaseRecipeAttributeViewSet):
    """
    ViewSet for managing the authenticated user's ingredients.

    Extends ``BaseRecipeAttributeViewSet`` to inherit token authentication,
    ``IsAuthenticated`` permission enforcement, and user-scoped queryset
    filtering without repetition.  The three exposed actions — ``list``,
    ``update`` / ``partial_update``, and ``destroy`` — cover the ingredient
    management surface: ``create`` and ``retrieve`` are intentionally absent
    because ingredients are created implicitly when a recipe references them
    by name via ``RecipeSerializer._get_or_create_ingredients()``.

    ``serializer_class = IngredientSerializer`` wires all actions to the
    minimal ``id`` + ``name`` representation.  The ``# type: ignore[bad-override]``
    silences the pyrefly false positive triggered by narrowing the parent's
    ``type[BaseSerializer]`` annotation to the concrete
    ``type[IngredientSerializer]``.
    """

    serializer_class: type[IngredientSerializer] = IngredientSerializer  # type: ignore[bad-override]
    queryset = Ingredient.objects.all()
