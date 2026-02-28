"""Serializers for the recipe API."""

from rest_framework.serializers import ModelSerializer

from core.models import Recipe, Tag


class RecipeSerializer(ModelSerializer):
    """
    Serializer for listing and representing Recipe objects.

    ModelSerializer introspects the Recipe model's field definitions so field
    types, max_length constraints, and other validators are derived automatically.
    The inner Meta class is the configuration point controlling which model to
    introspect and which subset of fields to expose.

    The field list here — id, title, time_minutes, price, link — is a lightweight
    summary suitable for list endpoints where returning the full description text
    for every row would inflate payload size. A separate RecipeDetailSerializer
    can extend this class to include heavier fields (description, timestamps) for
    the single-object retrieve endpoint.

    `read_only_fields = ["id"]` prevents API consumers from supplying or
    overwriting the primary key. The id is assigned by the database on INSERT and
    must never be controlled by untrusted client input; marking it read-only causes
    DRF to ignore the field on write operations while still including it in the
    serialized response.

    The `# type: ignore[bad-override]` on the inner Meta class silences a
    pyrefly/mypy warning: ModelSerializer declares Meta without type stubs, so
    re-declaring it as a class attribute triggers a "bad-override" false positive
    even though this is the canonical DRF pattern.
    """

    class Meta:  # type: ignore[bad-override]
        model: type[Recipe] = Recipe
        fields: list[str] = ["id", "title", "time_minutes", "price", "link"]
        read_only_fields: list[str] = ["id"]


class RecipeDetailSerializer(RecipeSerializer):
    """
    Serializer for the single-object recipe detail endpoint.

    Extends RecipeSerializer so all list-safe fields (id, title, time_minutes,
    price, link) are inherited without repetition. The inner Meta subclasses
    RecipeSerializer.Meta directly, meaning both `model` and `read_only_fields`
    are already set and only `fields` needs to be widened.

    The additional field — `description` — is a TextField that may contain
    several kilobytes of text. Excluding it from the list serializer avoids
    inflating every row in a paginated list response; it is only fetched and
    serialized when a caller explicitly requests a single recipe by pk.

    `RecipeSerializer.Meta.fields + ["description"]` appends to the parent's
    field list at class definition time, keeping the field order predictable
    and making it obvious at a glance which extra fields the detail view exposes.
    """

    class Meta(RecipeSerializer.Meta):
        fields: list[str] = RecipeSerializer.Meta.fields + ["description"]


class TagSerializer(ModelSerializer):
    """
    Serializer for listing and representing Tag objects.

    A minimal serializer exposing only ``id`` and ``name`` — the complete set of
    fields on the Tag model.  Unlike RecipeSerializer / RecipeDetailSerializer,
    there is no "summary vs detail" split because Tag objects carry no heavy fields
    that would warrant a separate detail serializer; every response can safely
    include the full field set without inflating payload size.

    ``read_only_fields = ["id"]`` prevents API consumers from supplying or
    overwriting the primary key on write operations, while still including it in
    every serialized response for client-side identification and subsequent lookups.

    The ``# type: ignore[bad-override]`` on the inner Meta class silences the same
    pyrefly false positive as in RecipeSerializer: re-declaring Meta as a nested
    class attribute triggers a "bad-override" warning even though this is the
    canonical DRF pattern and carries no runtime risk.
    """

    class Meta:  # type: ignore[bad-override]
        model: type[Tag] = Tag
        fields: list[str] = ["id", "name"]
        read_only_fields: list[str] = ["id"]
