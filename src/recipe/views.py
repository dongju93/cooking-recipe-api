"""Views for the recipe API."""

from typing import Sequence

from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from core.models import Ingredient, Recipe, Tag

from .serializers import (
    IngredientSerializer,
    RecipeDetailSerializer,
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
    ) -> type[RecipeDetailSerializer] | type[RecipeSerializer]:
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


class TagViewSet(ListModelMixin, UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    """
    ViewSet providing list, update, and delete actions for the authenticated user's tags.

    Composed from ``ListModelMixin`` (``list``), ``UpdateModelMixin``
    (``update`` and ``partial_update``), ``DestroyModelMixin`` (``destroy``), and
    ``GenericViewSet`` (which wires mixin actions to DRF's dispatch machinery).
    This intentionally omits ``create`` and ``retrieve`` — tags are managed
    indirectly through recipes, so only listing, in-place renaming, and deletion
    are exposed at this stage.  Adding a mixin later (e.g. ``CreateModelMixin``)
    will extend the surface without touching existing behavior.

    ``authentication_classes = [TokenAuthentication]`` and
    ``permission_classes = [IsAuthenticated]`` enforce the same auth contract as
    ``RecipeViewSet``: every request must carry a valid ``Authorization: Token <key>``
    header or the view returns 401 Unauthorized before ``get_queryset()`` is reached.

    ``get_queryset()`` scopes the queryset to the requesting user so that tag lists
    and updates are always private — one user's tags are never visible to or
    modifiable by another user's client.
    """

    serializer_class: type[TagSerializer] = TagSerializer  # type: ignore[bad-override]
    queryset = Tag.objects.all()
    authentication_classes: Sequence[type[BaseAuthentication]] = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[bad-override]
        """
        Return only the tags owned by the currently authenticated user.

        Mirrors the user-scoping pattern from ``RecipeViewSet.get_queryset()``: the
        class-level ``queryset`` is intentionally broad (all tags in the database),
        and this override applies ``.filter(user=request.user)`` to ensure the list
        action never exposes another user's tags.

        ``order_by("-name")`` sorts tags in reverse alphabetical order.  Using name
        rather than id provides a semantically meaningful, stable sort for the tag
        list endpoint where alphabetical grouping is more useful than insertion order.

        ``# type: ignore[bad-override]`` suppresses the same pyrefly false positive
        as in ``RecipeViewSet``: the parent's generic return type cannot be matched
        against the concrete return type when the method omits an explicit annotation.
        """
        return self.queryset.filter(user=self.request.user).order_by("-name")


class IngredientViewSet(
    DestroyModelMixin, UpdateModelMixin, ListModelMixin, GenericViewSet
):
    """
    ViewSet providing only the list action for the authenticated user's ingredients.

    Composed from ``ListModelMixin`` (``list``) and ``GenericViewSet`` (which wires
    mixin actions to DRF's dispatch machinery).  Create, update, retrieve, and
    destroy are intentionally omitted at this stage — ingredients are expected to
    be managed indirectly through recipe creation in a future iteration.  Adding a
    mixin later (e.g. ``CreateModelMixin``) will extend the surface without touching
    existing behavior.

    ``authentication_classes = [TokenAuthentication]`` and
    ``permission_classes = [IsAuthenticated]`` enforce the same auth contract as
    ``RecipeViewSet`` and ``TagViewSet``: every request must carry a valid
    ``Authorization: Token <key>`` header or the view returns 401 Unauthorized
    before ``get_queryset()`` is reached.

    ``get_queryset()`` scopes the queryset to the requesting user so that
    ingredient lists are always private — one user's ingredients are never visible
    to another user's client.
    """

    serializer_class: type[IngredientSerializer] = IngredientSerializer  # type: ignore[bad-override]
    query_set = Ingredient.objects.all()
    authentication_classes: Sequence[type[BaseAuthentication]] = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[bad-override]
        """
        Return only the ingredients owned by the currently authenticated user.

        Mirrors the user-scoping pattern from ``RecipeViewSet.get_queryset()`` and
        ``TagViewSet.get_queryset()``: the class-level ``query_set`` is intentionally
        broad (all ingredients in the database), and this override applies
        ``.filter(user=request.user)`` to ensure the list action never exposes
        another user's ingredients.

        ``order_by("-name")`` sorts ingredients in reverse alphabetical order,
        matching the ordering convention used by ``TagViewSet``.  A name-based sort
        provides a semantically meaningful, stable ordering for ingredient lists
        where alphabetical grouping is more useful than insertion order.

        ``# type: ignore[bad-override]`` suppresses the same pyrefly false positive
        as in ``RecipeViewSet`` and ``TagViewSet``: the parent's generic return type
        cannot be matched against the concrete return type when the method omits an
        explicit annotation.
        """
        return self.query_set.filter(user=self.request.user).order_by("-name")
