"""Load Tweede Kamer 2025 election results into City/District/Neighborhood.

Reproducible ETL (both sources are CC0 and pinned by URL + checksum):

    uv run python manage.py load_election_stats            # all cities in DB
    uv run python manage.py load_election_stats --city 0518
    uv run python manage.py load_election_stats --dry-run

Source files are cached in ``--cache-dir`` (default: ``.election-cache/``
next to ``manage.py``) so re-runs are offline and deterministic. Results are
stored under the ``tk2025`` key of the ``election_stats`` JSON column —
deliberately separate from ``stats``, which the CBS refresh overwrites — and
served merged into ``stats`` by the API schemas.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from scraping.models import City, District, Neighborhood
from scraping.services import elections


class Command(BaseCommand):
    help = "Load TK2025 election results per buurt/wijk/gemeente from Kiesraad open data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            action="append",
            help="CBS gemeentecode (e.g. 0518); repeatable. Default: all cities in DB",
        )
        parser.add_argument("--cache-dir", type=Path, default=Path(__file__).resolve().parents[3] / ".election-cache")
        parser.add_argument(
            "--dry-run", action="store_true", help="Compute and report, but do not write to the database"
        )

    def handle(self, *args, **options):
        cities = City.objects.all().order_by("code")
        if options["city"]:
            cities = cities.filter(code__in=options["city"])
        if not cities.exists():
            self.stderr.write(self.style.ERROR("No matching cities in the database"))
            return

        votes_zip, locations_csv = elections.download_sources(options["cache_dir"])
        stations = elections.parse_votes(votes_zip)
        locations = elections.parse_locations(locations_csv)
        elections.attach_locations(stations, locations)

        now = timezone.now()
        for city in cities:
            city_stations = stations.get(city.code)
            if not city_stations:
                self.stderr.write(self.style.WARNING(f"{city.name} ({city.code}): no stations in Kiesraad data"))
                continue

            neighborhoods = list(Neighborhood.objects.filter(city=city).select_related("district"))
            result = elections.aggregate_city(city_stations, neighborhoods)

            self.stdout.write(
                f"{city.name} ({city.code}): {result.located_stations}/{result.total_stations} stations located, "
                f"{len(result.neighborhoods) - result.fallback_neighborhoods} buurten direct, "
                f"{result.fallback_neighborhoods} via wijk fallback, {result.empty_neighborhoods} empty"
            )
            if options["dry_run"]:
                continue

            self._store(city, result, now)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run — nothing written"))

    def _store(self, city: City, result: elections.CityElectionStats, now) -> None:
        def merge(obj, stats: dict) -> None:
            obj.election_stats = {**(obj.election_stats or {}), elections.ELECTION_KEY: stats}
            obj.election_stats_fetched_at = now
            obj.save(update_fields=["election_stats", "election_stats_fetched_at"])

        merge(city, result.city)
        for district in District.objects.filter(city=city):
            if district.code in result.districts:
                merge(district, result.districts[district.code])
        for neighborhood in Neighborhood.objects.filter(city=city):
            if neighborhood.code in result.neighborhoods:
                merge(neighborhood, result.neighborhoods[neighborhood.code])
