"""Views for the recipe API."""

from typing import Sequence

from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from core.models import Recipe

from .serializers import RecipeSerializer


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

    serializer_class: type[BaseSerializer] | None = RecipeSerializer
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
