"""Serializers for the recipe API."""

from rest_framework.serializers import ModelSerializer

from core.models import Recipe


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
