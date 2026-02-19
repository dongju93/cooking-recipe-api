"""Tests for the wait_for_db management command."""

# unittest.mock.patch: Decorator for temporarily replacing objects with mocks during tests.
# Used here to mock the database check method, preventing actual database connections.
from unittest.mock import patch

# django.core.management.call_command: Programmatically invokes Django management commands.
# Allows testing management commands like 'wait_for_db' without using the CLI.
from django.core.management import call_command

# django.db.utils.OperationalError: Django's generic database operational error.
# Raised when database operations fail (e.g., connection issues, query errors).
from django.db.utils import OperationalError

# django.test.SimpleTestCase: Lightweight test case that doesn't use the database.
# Faster than TestCase because it skips database setup/teardown - ideal for
# testing logic with mocked database interactions.
from django.test import SimpleTestCase

# psycopg.OperationalError: PostgreSQL-specific operational error from psycopg3 driver.
# Raised when psycopg encounters connection issues before Django's abstraction layer.
# Different from Django's OperationalError as it occurs at the driver level.
from psycopg import OperationalError as PsycopgError


@patch("core.management.commands.wait_for_db.Command.check")
class CommandTests(SimpleTestCase):
    """
    Tests for wait_for_db, which polls until the database is ready.

    SimpleTestCase is used instead of TestCase because these tests don't touch
    the real database — Command.check() is mocked out entirely, so no DB setup
    or teardown is needed. This makes the tests faster.

    The class-level @patch replaces Command.check() for every test method in this
    class. @patch injects the mock object as an extra argument; when applied at the
    class level it is always the last parameter (mock_connect here). This means each
    test exercises the command without triggering a real database connection.

    call_command("wait_for_db") invokes the management command programmatically,
    the same way Django's CLI would run `python manage.py wait_for_db`.
    """

    def test_wait_for_db_ready(self, mock_connect):
        """
        Database ready on first attempt — check() is called exactly once.

        mock_connect.return_value = True makes the mocked check() succeed immediately.
        assert_called_once_with(databases=["default"]) verifies that the command
        checked exactly the "default" database alias and did not retry.
        """
        mock_connect.return_value = True
        call_command("wait_for_db")
        mock_connect.assert_called_once_with(databases=["default"])

    @patch("time.sleep")
    def test_wait_for_db_delayed(self, mock_sleep, mock_connect):
        """
        Command retries when check() raises errors before eventually succeeding.

        side_effect accepts a list: each call to the mock raises or returns the next
        item in sequence. Two error types are used because database startup has two
        distinct failure stages:
          - PsycopgError: raised by the psycopg3 driver before Django's DB abstraction
            layer processes the connection (driver-level failure).
          - OperationalError: raised by Django when the connection is accepted but the
            database is not yet ready to serve queries (Django-level failure).
        The 6th call returns True, simulating a successful connection.

        @patch("time.sleep") prevents the command from actually sleeping between
        retries, keeping the test instant. Decorators are applied bottom-to-top, so
        the inner @patch (time.sleep) is injected first as mock_sleep, and the
        outer class-level @patch (Command.check) is injected second as mock_connect.
        """
        mock_connect.side_effect = [PsycopgError] * 2 + [OperationalError] * 3 + [True]
        call_command("wait_for_db")
        self.assertEqual(mock_connect.call_count, 6)
        mock_connect.assert_called_with(databases=["default"])
        # Verify sleep was called 5 times (once for each failed attempt)
        self.assertEqual(mock_sleep.call_count, 5)
