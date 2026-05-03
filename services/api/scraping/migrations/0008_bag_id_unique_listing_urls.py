"""Make bag_id the unique identifier of Listing.

Steps:
1. Create the listing_urls table.
2. Backfill listing_urls from listings.detail_url + listings.website. When the
   pre-migration data has duplicate bag_ids (cross-portal duplicates — exactly
   the bug this PR is fixing), collapse each group onto its earliest-created
   row, attach every member's URL to that canonical row, and delete the
   non-canonical members.
3. Drop the website + detail_url columns from listings.
4. Drop the (website, created_at) index that's now homed on listing_urls.
5. Promote bag_id to NOT NULL UNIQUE — guaranteed safe by step 2.
6. Rename scrape_runs.listings_new to new_properties_count and add
   new_listing_urls_count.

Forward-only on populated databases: step 2 is destructive (drops duplicate
listing rows) and there's no way to reconstruct the pre-collapse state. The
reverse data step raises explicitly rather than pretending to roll back.
"""

from collections import defaultdict

from django.db import migrations, models

_FORWARD_ONLY_MESSAGE = (
    "Migration 0008 is forward-only on populated databases — collapsing duplicate "
    "bag_id rows is destructive and cannot be reconstructed."
)


def _backfill_listing_urls(apps, schema_editor):
    Listing = apps.get_model("scraping", "Listing")
    ListingUrl = apps.get_model("scraping", "ListingUrl")

    null_bag_count = Listing.objects.filter(bag_id__isnull=True).count()
    if null_bag_count:
        raise RuntimeError(
            f"Cannot migrate: {null_bag_count} listings have NULL bag_id. "
            "Backfill or delete them before applying migration 0008."
        )

    grouped: dict[str, list] = defaultdict(list)
    for listing in Listing.objects.all().order_by("created_at", "id"):
        grouped[listing.bag_id].append(listing)

    new_urls = []
    non_canonical_ids = []
    for members in grouped.values():
        canonical = members[0]
        for member in members:
            new_urls.append(
                ListingUrl(
                    listing_id=canonical.id,
                    url=member.detail_url,
                    website=member.website,
                    first_seen_at=member.created_at,
                )
            )
            if member.id != canonical.id:
                non_canonical_ids.append(member.id)

    ListingUrl.objects.bulk_create(new_urls, batch_size=500)
    if non_canonical_ids:
        Listing.objects.filter(id__in=non_canonical_ids).delete()


def _refuse_reverse(apps, schema_editor):
    raise RuntimeError(_FORWARD_ONLY_MESSAGE)


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0007_deadlisting"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingUrl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "website",
                    models.CharField(
                        choices=[("funda", "Funda"), ("pararius", "Pararius"), ("vastgoed_nl", "VastgoedNL")],
                        max_length=20,
                    ),
                ),
                ("url", models.URLField(max_length=500, unique=True)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="listing_urls",
                        to="scraping.listing",
                    ),
                ),
            ],
            options={
                "db_table": "listing_urls",
                "indexes": [
                    models.Index(fields=["website", "first_seen_at"], name="idx_listing_urls_website"),
                ],
            },
        ),
        migrations.RunPython(_backfill_listing_urls, reverse_code=_refuse_reverse),
        migrations.RemoveIndex(
            model_name="listing",
            name="idx_listings_website_created",
        ),
        migrations.RemoveField(
            model_name="listing",
            name="detail_url",
        ),
        migrations.RemoveField(
            model_name="listing",
            name="website",
        ),
        migrations.AlterField(
            model_name="listing",
            name="bag_id",
            field=models.CharField(max_length=16, unique=True),
        ),
        migrations.RenameField(
            model_name="scraperun",
            old_name="listings_new",
            new_name="new_properties_count",
        ),
        migrations.AddField(
            model_name="scraperun",
            name="new_listing_urls_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
