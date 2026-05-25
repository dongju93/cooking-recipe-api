"""Serializers for the recipe API."""

from typing import Any, ClassVar

from rest_framework.serializers import ModelSerializer

from core.models import Ingredient, Recipe, Tag


class IngredientSerializer(ModelSerializer):
    """
    Serializer for listing and representing Ingredient objects.

    A minimal serializer exposing only ``id`` and ``name`` — the complete set of
    fields on the Ingredient model.  No "summary vs detail" split is needed
    because Ingredient objects carry no heavy fields that would warrant a
    separate detail serializer; every response can safely include the full
    field set without inflating payload size.

    ``read_only_fields = ["id"]`` prevents API consumers from supplying or
    overwriting the primary key on write operations, while still including it in
    every serialized response for client-side identification and subsequent lookups.

    The ``# type: ignore[bad-override]`` on the inner Meta class silences the
    pyrefly false positive triggered when a nested ``Meta`` class attribute is
    re-declared in a ModelSerializer subclass — this is the canonical DRF pattern
    and carries no runtime risk.
    """

    class Meta:  # type: ignore[bad-override]
        model: type[Ingredient] = Ingredient
        fields: list[str] = ["id", "name"]
        read_only_fields: list[str] = ["id"]


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

    tags = TagSerializer(many=True, required=False)
    ingredients = IngredientSerializer(many=True, required=False)

    class Meta:  # type: ignore[bad-override]
        model: type[Recipe] = Recipe
        fields: list[str] = [
            "id",
            "title",
            "time_minutes",
            "price",
            "link",
            "tags",
            "ingredients",
        ]
        read_only_fields: list[str] = ["id"]

    def _get_or_create_tags(self, tags: list[dict[str, str]], recipe: Recipe) -> None:
        """
        Resolve tag dicts to Tag ORM instances and attach them to a recipe.

        Extracted as a private helper so both ``create()`` and ``update()`` can
        share identical tag-resolution logic without duplication.

        ``self.context["request"].user`` is used rather than ``recipe.user``
        because during ``create()`` the recipe row has just been saved and its
        ``user`` FK is set correctly, but during ``update()`` using the request
        context is the canonical pattern for accessing the authenticated user —
        it avoids an extra DB hit to refresh the instance and stays consistent
        regardless of whether the caller passes a newly-created or pre-existing
        recipe.

        ``Tag.objects.get_or_create(user=auth_user, name=...)`` enforces
        per-user tag uniqueness: if a matching tag already exists it is reused
        rather than duplicated, keeping tag management idempotent across
        multiple recipe writes that reference the same label.
        """
        auth_user = self.context["request"].user
        for tag in tags:
            tag_obj, _ = Tag.objects.get_or_create(user=auth_user, name=tag["name"])
            recipe.tags.add(tag_obj)

    def _get_or_create_ingredients(
        self, ingredients: list[dict[str, str]], recipe: Recipe
    ) -> None:
        """
        Resolve ingredient dicts to Ingredient ORM instances and attach them to a recipe.

        Mirrors the design of ``_get_or_create_tags()``: extracted as a private
        helper so both ``create()`` and ``update()`` share the same
        ingredient-resolution logic without duplication.

        ``self.context["request"].user`` is used as the owner rather than
        ``recipe.user`` for the same reasons as in ``_get_or_create_tags()``:
        it is the canonical DRF pattern for accessing the authenticated user
        inside a serializer, avoids an extra DB hit, and remains consistent
        whether the recipe is freshly created or pre-existing.

        ``Ingredient.objects.get_or_create(user=auth_user, name=...)`` enforces
        per-user ingredient uniqueness: if a matching ingredient already exists
        it is reused rather than duplicated, keeping ingredient management
        idempotent across multiple recipe writes that reference the same label.
        """
        auth_user = self.context["request"].user
        for ingredient in ingredients:
            ingredient_obj, _ = Ingredient.objects.get_or_create(
                user=auth_user, name=ingredient["name"]
            )
            recipe.ingredients.add(ingredient_obj)

    def create(self, validated_data: dict[str, Any]) -> Recipe:
        """
        Persist a new Recipe and associate any supplied tags.

        DRF's default ``ModelSerializer.create()`` calls
        ``Model.objects.create(**validated_data)`` directly, which fails for M2M
        or nested relations because the ORM cannot resolve them from a plain
        dict.  Overriding ``create()`` provides a hook to extract the nested
        ``tags`` list before delegating scalar-field creation to
        ``super().create()``.

        ``validated_data.pop("tags", [])`` removes the key before the
        ``super()`` call so the parent does not encounter an unexpected keyword
        argument.  The default of ``[]`` handles the case where the client omits
        the field entirely — ``required=False`` on the ``tags`` field means it
        may be absent from ``validated_data`` altogether.

        Tag resolution is delegated to ``_get_or_create_tags()``, which is
        shared with ``update()`` to keep both write paths consistent.
        """
        tags: list[dict[str, str]] = validated_data.pop("tags", [])
        ingredients = validated_data.pop("ingredients", [])
        recipe: Recipe = super().create(validated_data)
        self._get_or_create_tags(tags, recipe)
        self._get_or_create_ingredients(ingredients, recipe)

        return recipe

    def update(self, instance: Recipe, validated_data: dict[str, Any]) -> Recipe:
        """
        Apply a partial or full update to an existing Recipe.

        DRF's default ``ModelSerializer.update()`` cannot handle M2M or nested
        relations from a plain dict for the same reason as ``create()``, so this
        override handles the ``tags`` field explicitly before falling back to
        ``setattr`` for all remaining scalar fields.

        The ``tags`` key is popped with a sentinel default of ``None`` to
        distinguish two intentionally different client behaviors:

        - **Key absent** (``None``) — the caller did not mention tags at all,
          e.g. a PATCH updating only ``title``.  The existing M2M set is left
          untouched.
        - **Key present, empty list** (``[]``) — the caller explicitly wants all
          tags removed.  ``instance.tags.clear()`` is called and no tags are
          re-added, resulting in a recipe with zero tags.
        - **Key present, non-empty list** — the M2M set is replaced wholesale:
          ``clear()`` first, then ``_get_or_create_tags()`` adds the new set.

        ``instance.save()`` is called explicitly rather than relying on
        ``super().update()`` because once the nested field is handled manually,
        the remaining ``validated_data`` contains only flat scalar fields that
        are safely applied with ``setattr``.
        """
        tags: list[dict[str, str]] | None = validated_data.pop("tags", None)
        ingredients: list[dict[str, str]] | None = validated_data.pop(
            "ingredients", None
        )

        if tags is not None:
            instance.tags.clear()
            self._get_or_create_tags(tags, instance)

        if ingredients is not None:
            instance.ingredients.clear()
            self._get_or_create_ingredients(ingredients, instance)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


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


class RecipeImageSerializer(ModelSerializer):
    """
    Serializer for uploading an image to an existing Recipe.

    Scoped to ``id`` and ``image`` only — intentionally narrower than
    ``RecipeDetailSerializer`` — so the upload endpoint cannot accept or modify
    any other recipe field.  This makes the contract explicit: the only mutable
    field through this serializer is ``image``.

    ``extra_kwargs = {"image": {"required": True}}`` overrides the field-level
    ``required`` attribute at the serializer layer.  The underlying model field
    has ``blank=True`` (optional at the DB level for recipes that have no image
    yet), but for the upload action it makes no sense to POST without a file,
    so the serializer enforces presence before ``is_valid()`` returns ``True``.

    ``ClassVar`` annotations on the Meta attributes prevent pyrefly from
    treating them as instance attributes rather than class-level configuration
    keys, which is the correct semantics for DRF's inner Meta class.

    The ``# type: ignore[bad-override]`` on the inner Meta class silences the
    same pyrefly false positive as in the other serializers: re-declaring Meta
    as a nested class attribute triggers a "bad-override" warning even though
    this is the canonical DRF pattern and carries no runtime risk.
    """

    class Meta:  # type: ignore[bad-override]
        model: type[Recipe] = Recipe
        fields: ClassVar[list[str]] = ["id", "image"]
        read_only_fields: ClassVar[list[str]] = ["id"]
        extra_kwargs: ClassVar[dict[str, dict[str, bool]]] = {
            "image": {"required": True}
        }
