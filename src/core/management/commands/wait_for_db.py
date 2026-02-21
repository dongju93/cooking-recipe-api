from time import sleep

from django.core.management.base import BaseCommand
from django.db.utils import OperationalError
from psycopg import OperationalError as PsycopgError


class Command(BaseCommand):
    """Django management command that blocks until the default database is ready.

    Django Management Commands
    --------------------------
    A management command is a Python module placed at:
        <app>/management/commands/<command_name>.py

    Django auto-discovers any such module containing a ``Command`` class that
    subclasses ``django.core.management.base.BaseCommand``. Once discovered,
    the command becomes available via:
        python manage.py <command_name>

    Key lifecycle hooks provided by ``BaseCommand``:
      - ``add_arguments(parser)`` — register CLI arguments (optional).
      - ``handle(*args, **options)`` — the main entry point; called after
        argument parsing and framework setup are complete.

    Built-in conveniences available inside ``handle``:
      - ``self.stdout`` / ``self.stderr`` — stream wrappers that respect the
        ``--no-color`` / ``--force-color`` flags.
      - ``self.style.*`` — ANSI colour helpers (e.g. ``self.style.SUCCESS``).
      - ``self.check(databases=[...])`` — runs Django's full system-check
        framework for the given databases before proceeding.

    This command is invoked at container/server startup (see ``dev_server.sh``
    and the Docker Compose entrypoint) to guarantee the database is accepting
    connections before ``migrate`` and ``runserver`` execute.
    """

    def handle(self, *args, **options) -> str | None:
        self.stdout.write("Waiting for database...")
        db_conn: bool = False

        while not db_conn:
            try:
                self.check(databases=["default"])
                db_conn = True
            except (PsycopgError, OperationalError) as e:
                self.stdout.write(f"Database unavailable, waiting 1 second... ({e})")
                sleep(1)

        self.stdout.write(self.style.SUCCESS("Database available!"))
