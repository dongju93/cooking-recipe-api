"""
Test suite for the wait_for_db management command.

This module tests the database connection waiting logic to ensure
the application waits for the database to be ready before starting.
"""

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
    Test cases for the wait_for_db management command.

    The @patch decorator at the class level applies to all test methods,
    automatically injecting 'mock_connect' as the last parameter to each test.
    This mocks the Command.check() method which Django uses to verify database
    connectivity, allowing us to simulate various database connection scenarios.
    """

    def test_wait_for_db_ready(self, mock_connect):
        """
        Test that wait_for_db returns immediately when database is ready.

        Scenario: Database is available on the first connection attempt.

        How it works:
        - mock_connect.return_value = True: Simulates successful database check
        - call_command("wait_for_db"): Executes the management command
        - assert_called_once_with(): Verifies the check was called exactly once
          with database=["default"], confirming no retries occurred

        This tests the happy path where the database is already available.
        """
        mock_connect.return_value = True
        call_command("wait_for_db")
        mock_connect.assert_called_once_with(databases=["default"])

    @patch("time.sleep")
    def test_wait_for_db_delayed(self, mock_sleep, mock_connect):
        """
        Test that wait_for_db retries when database is not immediately available.

        Scenario: Database connection fails multiple times before succeeding.

        How it works:
        - @patch("time.sleep"): Mocks sleep() to prevent actual waiting,
          making tests run instantly instead of waiting for real retry delays
        - mock_connect.side_effect: Defines a sequence of return values:
          * [PsycopgError] * 2: First 2 calls raise driver-level errors
            (psycopg3 not ready)
          * [OperationalError] * 3: Next 3 calls raise Django-level errors
            (database accepting connections but not fully ready)
          * [True]: 6th call succeeds, database is ready
        - call_count == 6: Verifies the command retried correctly
        - mock_sleep is injected first, mock_connect second due to
          decorator order (applied bottom-to-top, injected right-to-left)

        This tests resilience to database startup delays, common in
        containerized environments where the database container may start
        before it's ready to accept connections.
        """
        mock_connect.side_effect = [PsycopgError] * 2 + [OperationalError] * 3 + [True]
        call_command("wait_for_db")
        self.assertEqual(mock_connect.call_count, 6)
        mock_connect.assert_called_with(databases=["default"])
        # Verify sleep was called 5 times (once for each failed attempt)
        self.assertEqual(mock_sleep.call_count, 5)
