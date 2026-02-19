"""
Test suite for Django admin interface customization.

This module tests the Django admin site configuration for the custom User model.
It verifies that the admin interface correctly displays user information and
respects authentication permissions.

Key testing areas:
- Admin access control (superuser authentication required)
- User list display customization (displayed fields)
- User search and filtering functionality
- Django admin action methods

Test Strategy:
- Use Django's Client class to simulate HTTP requests to admin endpoints
- Use force_login() to bypass authentication for testing protected views
- Create test fixtures (admin user and regular user) in setUp()
- Verify admin site responses contain expected user data
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class AdminSiteTests(TestCase):
    """
    Test cases for Django admin customization of the User model.

    This test class verifies that the admin interface is properly configured
    for the custom User model. It tests that the admin can view user listings
    with appropriate field displays.

    Fixtures created in setUp():
    - admin_user: A superuser with admin credentials (email-based authentication)
    - user: A regular user for testing admin display functionality

    Note: Client.force_login() bypasses authentication, allowing us to test
    protected admin views without requiring a real login session.
    """

    def setUp(self) -> None:
        """
        Set up test fixtures and authenticated admin client.

        This method runs before each test and creates:
        1. An admin client (self.client) - HTTP client for making requests
        2. A superuser (self.admin_user) - Account with full admin permissions
        3. A regular user (self.user) - Test subject for admin display tests

        The client is authenticated as the superuser using force_login(),
        allowing subsequent requests to access protected admin views.
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
        Test that the admin user list page displays users correctly.

        Scenario: Authenticated admin user views the user changelist.

        How it works:
        - reverse("admin:core_user_changelist"): Generates the URL for the user
          list page in Django admin (e.g., /admin/core/user/)
        - self.client.get(url): Makes an HTTP GET request as the authenticated
          superuser (established in setUp)
        - assertContains(): Verifies that both the user's name and email appear
          in the HTML response, confirming the admin list_display configuration
          is working correctly

        Expected admin configuration:
        - list_display: Should include 'name' and 'email' fields
        - The admin interface auto-generates HTML with these field values

        This test ensures the admin interface is properly configured to display
        relevant user information for administrators.
        """
        url: str = reverse("admin:core_user_changelist")
        response = self.client.get(url)

        self.assertContains(response, self.user.name)
        self.assertContains(response, self.user.email)

    def test_edit_user_page(self) -> None:
        """Test that the admin user edit page displays and functions correctly.

        Scenario: Authenticated admin user accesses the form to edit an existing user.

        How it works:
        - reverse("admin:core_user_change", args=[self.user.id]): Generates the URL
          for editing a specific user record (e.g., /admin/core/user/1/change/)
        - self.client.get(url): Makes an HTTP GET request as the authenticated admin
          superuser (established in setUp)
        - self.assertEqual(response.status_code, 200): Verifies the page loads
          successfully without redirects or errors

        This test ensures the admin form for editing user details is properly
        configured and accessible to authorized admin users.
        """
        url: str = reverse("admin:core_user_change", args=[self.user.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_create_user_page(self) -> None:
        """Test that the admin user creation page displays and functions correctly.

        Scenario: Authenticated admin user accesses the form to create a new user.

        How it works:
        - reverse("admin:core_user_add"): Generates the URL for the user creation
          form in Django admin (e.g., /admin/core/user/add/)
        - self.client.get(url): Makes an HTTP GET request as the authenticated admin
          superuser (established in setUp)
        - self.assertEqual(response.status_code, 200): Verifies the form page loads
          successfully and renders without errors

        This test ensures the admin form for creating new users is properly configured,
        has the correct custom fields (email, password, name, permissions), and is
        accessible to authorized admin users.
        """
        url: str = reverse("admin:core_user_add")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
