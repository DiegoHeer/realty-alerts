import re
from datetime import UTC, datetime

from django.db import migrations

_BATCH = 500
_FIELDS = ["bedroom_count", "bathroom_count", "surface_area_m2", "build_year"]


def _parse_build_year(construction_period):
    if not construction_period:
        return None
    match = re.search(r"\d{4}", construction_period)
    return int(match.group()) if match else None


def backfill(apps, schema_editor):
    Residence = apps.get_model("scraping", "Residence")
    Listing = apps.get_model("scraping", "Listing")
    min_ts = datetime.min.replace(tzinfo=UTC)

    pending = []
    for residence in Residence.objects.all().iterator():
        resolved = list(Listing.objects.filter(residence=residence, bag_status="resolved"))
        if not resolved:
            continue
        freshest = max(resolved, key=lambda listing: listing.list_scraped_at or min_ts)
        residence.bedroom_count = freshest.bedroom_count
        residence.bathroom_count = freshest.bathroom_count
        residence.surface_area_m2 = freshest.surface_area_m2
        residence.build_year = _parse_build_year(freshest.construction_period)
        pending.append(residence)
        if len(pending) >= _BATCH:
            Residence.objects.bulk_update(pending, _FIELDS)
            pending = []
    if pending:
        Residence.objects.bulk_update(pending, _FIELDS)


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0027_residence_listing_attrs"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
