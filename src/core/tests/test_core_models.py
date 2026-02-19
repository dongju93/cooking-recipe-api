"""
Test suite for the core application models.

This module contains comprehensive tests for the custom User model defined
in the core application. It validates user creation, email normalization,
password hashing, and superuser functionality.

Key testing areas:
- User creation with email and password
- Email normalization (case-insensitive domain handling)
- Password validation and hashing
- Superuser creation with proper permissions
- Error handling for invalid inputs (e.g., empty email)
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import User


class ModelTests(TestCase):
    """
    Test cases for the custom User model.

    The custom User model is the primary authentication entity in this application.
    Unlike Django's default User model (which uses username), this implementation
    requires email for authentication. This test class verifies all core functionality.

    Test Strategy:
    - Use get_user_model() to access the custom User model dynamically
    - Type ignore comments are added where pyrefly cannot resolve the custom
      manager's create_user() and create_superuser() methods
    - All tests use TestCase (not SimpleTestCase) because they require database access
    """

    def test_create_user_with_email_successful(self) -> None:
        """
        Test successful user creation with email and password.

        Scenario: Creating a new user with valid email and password.

        How it works:
        - create_user() creates a new User instance and saves it to the database
        - self.assertEqual(user.email, email): Verifies the email is stored exactly
          as provided (respecting case at this point; normalization is tested separately)
        - self.assertTrue(user.check_password(password)): Confirms the password is
          hashed and stored securely (not stored in plaintext)

        This is the primary happy-path test for user creation,
        ensuring the core authentication mechanism works correctly.
        """
        email: str = "test@example.com"
        password: str = "testpass123"
        user: User = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email=email, password=password
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self) -> None:
        """
        Test that email domains are normalized to lowercase.

        Scenario: User registration with emails in various case combinations.

        How it works:
        - Email normalization converts the domain portion to lowercase for consistent
          lookups and to prevent duplicate accounts from case variations
        - The local part (before @) preserves case, as email addresses are technically
          case-insensitive in practice but this is the standard approach
        - mock_emails list contains 10 test cases covering:
          * All uppercase domains (EXAMPLE.com, GMAIL.COM)
          * Mixed case domains (Example.com, Test.Co.Uk)
          * Email addresses with special characters (support+tag@, John.Doe@)
          * Various TLDs (.com, .org, .net, .io, .co.uk)
        - For each case, we create the user and verify the domain is normalized

        This test ensures case-insensitive email lookups work correctly and
        prevents multiple accounts for the same email address.

        Note: Email normalization follows RFC 5321 standards where the domain
        is case-insensitive but the local part may be case-sensitive depending
        on the email provider (we normalize both for safety).
        """
        mock_emails: list[list[str]] = [
            ["test1@EXAMPLE.com", "test1@example.com"],
            ["Test2@Example.com", "Test2@example.com"],
            ["TEST3@EXAMPLE.com", "TEST3@example.com"],
            ["test4@example.COM", "test4@example.com"],
            ["User@GMAIL.COM", "User@gmail.com"],
            ["ADMIN@COMPANY.ORG", "ADMIN@company.org"],
            ["Info@Test.Co.Uk", "Info@test.co.uk"],
            ["support+tag@DOMAIN.IO", "support+tag@domain.io"],
            ["John.Doe@EXAMPLE.NET", "John.Doe@example.net"],
            ["TEST_USER@MAIL.COM", "TEST_USER@mail.com"],
        ]
        for email, expected in mock_emails:
            user: User = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
                email=email, password="mock123"
            )
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raise_error(self) -> None:
        """
        Test that creating a user without an email raises a ValueError.

        Scenario: Attempting to create a user with an empty email string.

        How it works:
        - Email is a required field in the custom User model manager
        - self.assertRaises(ValueError): Verifies that create_user() raises ValueError
          when an empty email string is provided
        - This prevents creating users without a valid authentication identifier

        This test ensures data integrity by preventing invalid user records.
        Since email is the unique identifier for authentication (not username),
        this validation is critical to the security model.
        """
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(  # type: ignore[missing-attribute]
                email="", password="test123"
            )

    def test_create_superuser(self) -> None:
        """
        Test successful superuser creation with proper permissions.

        Scenario: Creating an admin/superuser account for system administration.

        How it works:
        - create_superuser() creates a User instance with elevated privileges
        - self.assertTrue(user.is_superuser): Verifies the is_superuser flag is True,
          which grants access to protected admin operations
        - self.assertTrue(user.is_staff): Verifies the is_staff flag is True,
          which allows access to Django's admin interface
        - Unlike create_user(), create_superuser() automatically sets both flags

        This test ensures the admin account creation mechanism works correctly.
        Superusers have unrestricted access to all models and the admin interface,
        so this functionality is critical for system administration.
        """
        user = get_user_model().objects.create_superuser(  # type: ignore[missing-attribute]
            email="superuser@example.com", password="superpass123"
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
