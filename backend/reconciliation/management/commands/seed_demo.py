"""Load the demo CSVs from data/ and run a reconciliation.

Usage:
    python manage.py seed_demo

This is the quickest path from a clean database to a populated dashboard.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from reconciliation.models import File
from reconciliation.services.file_service import DuplicateFileError, import_file
from reconciliation.services.run_service import create_run


class Command(BaseCommand):
    help = "Import data/internal.csv and data/external.csv and run reconciliation."

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[4]
        data_dir = repo_root / "data"
        internal_path = data_dir / "internal.csv"
        external_path = data_dir / "external.csv"

        files = {}
        for name, source, path in (
            ("internal.csv", "INTERNAL", internal_path),
            ("external.csv", "EXTERNAL", external_path),
        ):
            content_bytes = path.read_bytes()
            content = content_bytes.decode("utf-8")
            try:
                f = import_file(filename=name, source=source, content=content, content_bytes=content_bytes)
                files[source] = f
                self.stdout.write(self.style.SUCCESS(f"Imported {name} ({f.record_count} records)."))
            except DuplicateFileError as exc:
                files[source] = exc.existing_file
                self.stdout.write(self.style.WARNING(str(exc)))

        if files.get("INTERNAL") and files.get("EXTERNAL"):
            run = create_run(
                internal_file_id=files["INTERNAL"].id,
                external_file_id=files["EXTERNAL"].id,
            )
            self.stdout.write(self.style.SUCCESS(f"Run #{run.id} complete: {run.summary}"))
            self.stdout.write(
                self.style.SUCCESS(
                    "Open http://localhost:5174 to view the dashboard."
                )
            )
        else:
            self.stdout.write(self.style.ERROR("Both an internal and an external file are required."))