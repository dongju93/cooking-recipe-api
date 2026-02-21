"""Views for the user API."""

from typing import Sequence

from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import CreateAPIView
from rest_framework.serializers import BaseSerializer, Serializer
from rest_framework.settings import api_settings

from .serializers import AuthTokenSerializer, UserSerializer


class CreateUserView(CreateAPIView):
    """
    API view to register a new user account via HTTP POST.

    CreateAPIView is a DRF generic view that provides a single `post()` handler.
    Internally it mixes in CreateModelMixin (which implements `create()`) and
    GenericAPIView (which wires up the serializer and response helpers).

    The full request lifecycle for POST /api/user/create:
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

    serializer_class: type[Serializer] = AuthTokenSerializer
    renderer_classes: Sequence[str] = api_settings.DEFAULT_RENDERER_CLASSES  # type: ignore[bad-override]
