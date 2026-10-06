from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from signage.content import lint
from signage.content.loader import FILES, load_all


class Command(BaseCommand):
    help = "Import content/*.yaml into the database (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=str(settings.SIGNAGE_CONTENT_DIR),
            help="Directory holding the YAML files.",
        )
        parser.add_argument(
            "--only",
            action="append",
            choices=sorted(FILES),
            help="Load only this file. Repeatable.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace rows that were edited in the admin, including the event.",
        )

    def handle(self, *args, **options):
        directory = Path(options["dir"])
        if not directory.is_dir():
            raise CommandError(f"{directory} is not a directory")
        try:
            report = load_all(
                directory,
                only=set(options["only"] or []) or None,
                overwrite=options["overwrite"],
            )
        except lint.LintError as error:
            raise CommandError(f"content lint failed: {error}") from error
        for item in report.skipped:
            self.stdout.write(self.style.WARNING(f"skipped {item}"))
        self.stdout.write(self.style.SUCCESS(report.summary()))
