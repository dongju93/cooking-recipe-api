"""Tests for Django admin customisation of the User model."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AdminSiteTests(TestCase):
    """
    Tests that the admin interface is configured correctly for the custom User model.

    Client() is Django's built-in HTTP test client. It simulates browser requests
    against the application without starting a real server, and tracks session and
    authentication state between calls.

    force_login(user) authenticates the client as the given user by directly writing
    the session cookie, bypassing the login form. This is the recommended approach
    for testing views that require authentication — it's faster than posting
    credentials and avoids coupling tests to the login view.

    reverse("admin:<app>_<model>_<action>") resolves admin URLs by name. The admin
    site auto-registers URL names in the format admin:<app_label>_<model_name>_<action>
    (e.g. "admin:core_user_changelist" → /admin/core/user/).
    """

    def setUp(self) -> None:
        """
        Create an authenticated admin client, a superuser, and a regular test user.

        setUp() runs before each test method. self.client is authenticated as
        admin_user, so all subsequent requests in the test are made as that superuser.
        self.user is the regular user used as a test subject in the assertions.
        """
        self.client = Client()
        self.admin_user = get_user_model().objects.create_superuser(  # type: ignore[missing-attribute]
            email="admin@example.com", password="adminpass123"
        )
        self.client.force_login(self.admin_user)

        self.user = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email="user@example.com", password="userpass123", name="Test User"
        )

    def test_users_list(self) -> None:
        """
        Changelist page contains the test user's name and email.

        The changelist is the admin list view for a model (/admin/core/user/).
        assertContains(response, text) checks that the response has HTTP 200 and
        that the given text appears in the HTML body. Finding both name and email
        confirms that list_display is configured to include both fields.
        """
        url: str = reverse("admin:core_user_changelist")
        response = self.client.get(url)

        self.assertContains(response, self.user.name)  # type: ignore[missing-attribute]
        self.assertContains(response, self.user.email)

    def test_edit_user_page(self) -> None:
        """
        User edit page loads without errors (HTTP 200).

        reverse("admin:core_user_change", args=[id]) generates the URL for editing
        a specific record (/admin/core/user/<id>/change/). HTTP 200 confirms that
        fieldsets contains no missing or misspelled field names — a bad field name
        would raise a FieldError and return a 500 response.
        """
        url: str = reverse("admin:core_user_change", args=[self.user.id])  # type: ignore[missing-attribute]
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_user_page(self) -> None:
        """
        User creation page loads without errors (HTTP 200).

        reverse("admin:core_user_add") generates the URL for the creation form
        (/admin/core/user/add/). HTTP 200 confirms that add_fieldsets is valid —
        a typo in a field name inside the tuple would raise a FieldError and
        return a 500 response instead.
        """
        url: str = reverse("admin:core_user_add")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
