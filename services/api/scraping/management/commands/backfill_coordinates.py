import time

from django.core.management.base import BaseCommand
from loguru import logger

from scraping.models import Residence
from scraping.resolvers.location import PdokLocationLookup


class Command(BaseCommand):
    help = "Backfill latitude/longitude for residences missing coordinates"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100, help="Residences per batch (default: 100)")
        parser.add_argument("--sleep", type=float, default=0.1, help="Seconds between batches (default: 0.1)")

    def handle(self, *args, **options):
        batch_size: int = options["batch_size"]
        sleep_seconds: float = options["sleep"]

        qs = Residence.objects.filter(latitude__isnull=True).exclude(bag_id="")
        total = qs.count()
        if total == 0:
            self.stdout.write("All residences already have coordinates.")
            return

        self.stdout.write(f"Backfilling coordinates for {total} residence(s)...")

        enriched = 0
        failed = 0

        with PdokLocationLookup() as lookup:
            for offset in range(0, total, batch_size):
                batch = list(qs[offset : offset + batch_size])
                if not batch:
                    break

                to_update: list[Residence] = []
                for residence in batch:
                    result = lookup.lookup(residence.bag_id)
                    if result is not None:
                        residence.latitude, residence.longitude = result.latitude, result.longitude
                        to_update.append(residence)
                        enriched += 1
                    else:
                        failed += 1

                if to_update:
                    Residence.objects.bulk_update(to_update, ["latitude", "longitude"])

                logger.info(f"Backfilled {enriched}/{total} residences ({failed} failures)")

                if offset + batch_size < total:
                    time.sleep(sleep_seconds)

        self.stdout.write(f"Done. Enriched {enriched}/{total}, failed {failed}.")
