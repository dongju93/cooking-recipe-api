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

from django.urls import path
from django.urls.resolvers import URLPattern

from .views import RecipeViewSet

app_name = "recipe"

_list = RecipeViewSet.as_view({"get": "list", "post": "create"})
_detail = RecipeViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns: list[URLPattern] = [
    path("", _list, name="recipe-list"),
    path("/<int:pk>", _detail, name="recipe-detail"),
]
