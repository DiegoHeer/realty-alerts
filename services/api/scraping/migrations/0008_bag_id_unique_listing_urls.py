"""Make bag_id the unique identifier of Listing.

Steps:
1. Create the listing_urls table.
2. Backfill listing_urls from listings.detail_url + listings.website (one row each).
3. Drop the website + detail_url columns from listings.
4. Drop the (website, created_at) index that's now homed on listing_urls.
5. Promote bag_id to NOT NULL UNIQUE (no backfill needed; confirmed no NULL rows).
6. Rename scrape_runs.listings_new to new_properties_count and add new_listing_urls_count.

The reverse migration restores detail_url/website on listings (filled from the
first listing_urls row), drops listing_urls, restores the original index, and
reverts bag_id to nullable.
"""

from django.db import migrations, models


def _copy_detail_urls_to_listing_urls(apps, schema_editor):
    Listing = apps.get_model("scraping", "Listing")
    ListingUrl = apps.get_model("scraping", "ListingUrl")

    rows = [
        ListingUrl(
            listing_id=listing.id,
            url=listing.detail_url,
            website=listing.website,
            first_seen_at=listing.created_at,
        )
        for listing in Listing.objects.all()
    ]
    ListingUrl.objects.bulk_create(rows, batch_size=500)


def _restore_listing_detail_url_and_website(apps, schema_editor):
    Listing = apps.get_model("scraping", "Listing")
    ListingUrl = apps.get_model("scraping", "ListingUrl")

    for listing in Listing.objects.all():
        first = ListingUrl.objects.filter(listing_id=listing.id).order_by("first_seen_at", "id").first()
        if first is None:
            continue
        listing.detail_url = first.url
        listing.website = first.website
        listing.save(update_fields=["detail_url", "website"])


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
        migrations.RunPython(
            _copy_detail_urls_to_listing_urls,
            reverse_code=_restore_listing_detail_url_and_website,
        ),
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
