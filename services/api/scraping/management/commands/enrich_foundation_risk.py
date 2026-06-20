from django.core.management.base import BaseCommand
from loguru import logger

from scraping.models import Residence
from scraping.tasks import enrich_foundation_risk


class Command(BaseCommand):
    help = "Dispatch foundation risk enrichment for residences missing this data"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Max residences to dispatch (default: 100)")
        parser.add_argument("--dry-run", action="store_true", help="Show count without dispatching")

    def handle(self, **options):
        qs = Residence.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            foundation_risk_fetched_at__isnull=True,
        )
        total = qs.count()
        batch_size = options["batch_size"]

        if options["dry_run"]:
            self.stdout.write(f"Would dispatch {min(total, batch_size)} of {total} residence(s)")
            return

        dispatched = 0
        for residence in qs[:batch_size]:
            enrich_foundation_risk.delay(residence.pk)
            dispatched += 1

        logger.info("Dispatched foundation risk enrichment for {} of {} residence(s)", dispatched, total)
        self.stdout.write(f"Dispatched {dispatched} of {total} residence(s)")
