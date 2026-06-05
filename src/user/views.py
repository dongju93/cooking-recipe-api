"""Views for the user API."""

from typing import Sequence

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from rest_framework.authentication import BaseAuthentication, TokenAuthentication
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.serializers import BaseSerializer
from rest_framework.settings import api_settings

from .serializers import AuthTokenSerializer, UserSerializer


class CreateUserView(CreateAPIView):
    """
    API view to register a new user account via HTTP POST.

    CreateAPIView is a DRF generic view that provides a single `post()` handler.
    Internally it mixes in CreateModelMixin (which implements `create()`) and
    GenericAPIView (which wires up the serializer and response helpers).

    The full request lifecycle for POST /api/v1/user/create:
      1. `post()` is called → delegates to `create()` in CreateModelMixin.
      2. `get_serializer(data=request.data)` instantiates UserSerializer with the
         incoming payload.
      3. `serializer.is_valid(raise_exception=True)` runs field-level and
         object-level validators. A 400 Bad Request is returned automatically if
         validation fails — no explicit error handling is needed here.
      4. `perform_create(serializer)` calls `serializer.save()`, which in turn
         calls `UserSerializer.create()` → `create_user()` → password hashing.
      5. A 201 Created response is returned with the serialized user data
         (password excluded because it is `write_only` in the serializer).

    No authentication or permission classes are set here, which means the
    endpoint inherits the project-level defaults from REST_FRAMEWORK settings.
    For a public registration endpoint, the project defaults should allow
    unauthenticated access (AllowAny), or `permission_classes = [AllowAny]`
    should be set explicitly.
    """

    serializer_class: type[BaseSerializer] | None = UserSerializer
    permission_classes = [AllowAny]


class CreateTokenView(ObtainAuthToken):
    """
    API view to issue a DRF authentication token via HTTP POST.

    Inherits from ObtainAuthToken, which already implements the `post()` handler:
    it calls `serializer.is_valid()`, then calls `Token.objects.get_or_create(user=…)`
    and returns `{"token": "<key>"}` in a 200 response. Subclassing lets us swap
    out just the two class attributes without duplicating any logic.

    `serializer_class` is replaced with AuthTokenSerializer so that our custom
    `validate()` method runs credential checking (email-based authenticate call
    + ValidationError on failure) instead of the default username/password check
    bundled with ObtainAuthToken.

    `renderer_classes` is set to api_settings.DEFAULT_RENDERER_CLASSES so the
    DRF browsable API renderer is available, matching the rest of the project's
    renderer configuration. ObtainAuthToken sets a narrower default (JSON only),
    so this override re-enables the HTML browsable interface for this endpoint.
    """

    serializer_class: type[AuthTokenSerializer] = AuthTokenSerializer  # type: ignore[bad-override]
    renderer_classes: Sequence[type[BaseRenderer]] = (
        api_settings.DEFAULT_RENDERER_CLASSES  # type: ignore[bad-assignment]
    )
    permission_classes = [AllowAny]


class ManageUserView(RetrieveUpdateAPIView):
    """
    API view for retrieving and updating the currently authenticated user.

    RetrieveUpdateAPIView is a DRF generic view that provides GET, PUT, and PATCH
    handlers. Internally it mixes in RetrieveModelMixin (implements `retrieve()`),
    UpdateModelMixin (implements `update()` / `partial_update()`), and
    GenericAPIView (wires serializer and response helpers).

    `get_object()` is overridden to return `request.user` directly instead of
    performing a queryset lookup. There is no URL pk — users always manage
    themselves. This also prevents IDOR: there is no identifier in the URL that
    a caller could manipulate to retrieve or modify another user's record.

    `authentication_classes = [TokenAuthentication]` requires `Authorization:
    Token <key>` in the request header. DRF verifies the token against the
    authtoken table and attaches the resolved User to `request.user`.

    `permission_classes = [IsAuthenticated]` short-circuits with 401 Unauthorized
    if the token is missing or invalid — the view logic is never reached for
    unauthenticated requests.
    """

    serializer_class: type[BaseSerializer] | None = UserSerializer
    authentication_classes: Sequence[type[BaseAuthentication]] = [TokenAuthentication]
    permission_classes = [
        IsAuthenticated
    ]  # cannot import private type alias, type hint is 'Sequence[_PermissionClass]'

    def get_object(self) -> AbstractBaseUser | AnonymousUser:
        """
        Return the currently authenticated user as the object to retrieve or update.

        DRF's GenericAPIView calls `get_object()` inside `retrieve()` and `update()`
        to resolve which model instance the current request targets. The default
        implementation performs a queryset lookup using the URL pk keyword argument.

        Returning `request.user` bypasses the queryset lookup entirely — there is no
        pk in the URL for this endpoint (the path is simply /api/v1/user/me). The user
        identified by the token is both the subject and the only accessible object,
        so no further filtering or permission check is needed beyond `IsAuthenticated`.
        """
        return self.request.user
