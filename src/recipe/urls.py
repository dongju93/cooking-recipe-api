"""URL configuration for the recipe API.

The ViewSet is wired manually (without a DRF router) because the router's
empty-prefix optimisation strips the ``/`` separator from the detail route,
producing ``api/v1/recipe<pk>`` instead of ``api/v1/recipe/<pk>``.

This URLconf is mounted at ``api/v1/recipe`` (no trailing slash) in app/urls.py.
Django strips that prefix and passes the remainder to these patterns:

  - ``""``      → list   (GET /api/v1/recipe) and create (POST /api/v1/recipe)
  - ``"/<pk>"`` → detail (GET, PUT, PATCH, DELETE /api/v1/recipe/<pk>)

``app_name = "recipe"`` declares the application namespace so URL names can be
reversed as ``"recipe:recipe-list"`` and ``"recipe:recipe-detail"``.
"""

from django.urls import include, path
from django.urls.resolvers import URLResolver
from rest_framework.routers import DefaultRouter

from .views import IngredientViewSet, RecipeViewSet, TagViewSet

app_name = "recipe"


router = DefaultRouter()
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("tags", TagViewSet, basename="tag")
router.register("ingredients", IngredientViewSet, basename="ingredient")

urlpatterns: list[URLResolver] = [
    path("", include(router.urls)),
]
