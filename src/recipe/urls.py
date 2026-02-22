"""URL configuration for the recipe API.

DRF's DefaultRouter generates two URL patterns automatically when a ViewSet
is registered:
  - ``recipes``        → list   (GET /recipes) and create (POST /recipes)
  - ``recipes/<pk>``   → detail (GET, PUT, PATCH, DELETE /recipes/<pk>)

``app_name = "recipe"`` declares the application namespace so that URL names can
be reversed unambiguously as ``"recipe:recipe-list"`` and ``"recipe:recipe-detail"``
even if another app registers URLs with the same action names. The router derives
these names from the basename of the registered ViewSet (defaulting to the queryset
model name in lowercase) combined with the action suffix (``-list``, ``-detail``).
"""

from django.urls import include, path
from django.urls.resolvers import URLResolver
from rest_framework.routers import DefaultRouter

from .views import RecipeViewSet

router = DefaultRouter()
router.register(r"recipes", RecipeViewSet)

app_name = "recipe"

urlpatterns: list[URLResolver] = [
    path("", include(router.urls)),
]
