"""URL configuration for the user API.

`app_name = "user"` sets the application namespace for this URL module.
Namespacing allows `reverse("user:create")` to resolve unambiguously even
if another app registers a URL also named "create". This namespace is
declared here and referenced via `include("user.urls")` in the root urls.py.
"""

from django.urls import path
from django.urls.resolvers import URLPattern

from .views import CreateTokenView, CreateUserView

app_name = "user"

urlpatterns: list[URLPattern] = [
    path("create", CreateUserView.as_view(), name="create"),
    path("token", CreateTokenView.as_view(), name="token"),
]
