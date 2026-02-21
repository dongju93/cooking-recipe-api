"""Views for the user API."""

from rest_framework.generics import CreateAPIView
from rest_framework.serializers import BaseSerializer

from .serializers import UserSerializer


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
