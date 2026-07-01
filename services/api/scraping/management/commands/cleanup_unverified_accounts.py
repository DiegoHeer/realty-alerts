from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from scraping.cleanup import UNVERIFIED_ACCOUNT_TTL_DAYS, delete_unverified_accounts


class Command(BaseCommand):
    help = (
        f"Hard-delete accounts that never verified their email within {UNVERIFIED_ACCOUNT_TTL_DAYS} days of signing up."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many accounts would be deleted without deleting them.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        count = delete_unverified_accounts(now=timezone.now(), dry_run=dry_run)
        verb = "Would delete" if dry_run else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} unverified account(s)."))
