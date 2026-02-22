"""Views for the recipe API."""

from typing import Sequence

from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models import Recipe

from .serializers import RecipeDetailSerializer, RecipeSerializer


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
