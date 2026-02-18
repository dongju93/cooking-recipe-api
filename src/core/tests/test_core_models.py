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
