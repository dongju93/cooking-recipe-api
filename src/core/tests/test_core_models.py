from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import User


class ModelTests(TestCase):
    def test_create_user_with_email_successful(self) -> None:
        email: str = "test@example.com"
        password: str = "testpass123"
        user: User = get_user_model().objects.create_user(  # type: ignore[missing-attribute]
            email=email, password=password
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self) -> None:
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
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(  # type: ignore[missing-attribute]
                email="", password="test123"
            )
