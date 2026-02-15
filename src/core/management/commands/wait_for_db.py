from time import sleep

from django.core.management.base import BaseCommand
from django.db.utils import OperationalError
from psycopg import OperationalError as PsycopgError


class Command(BaseCommand):
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
