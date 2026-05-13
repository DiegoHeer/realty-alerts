from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0005_rename_listing_to_residence"),
    ]

    # `migrations.RenameIndex` is a Django >= 4.1 op; ty / django-types stubs
    # don't list it yet, so each call carries `# ty: ignore[unresolved-attribute]`.
    operations = [
        migrations.RenameModel(
            old_name="ListingUrl",
            new_name="Listing",
        ),
        migrations.RenameField(
            model_name="listing",
            old_name="listing",
            new_name="residence",
        ),
        migrations.RenameField(
            model_name="scraperun",
            old_name="new_listing_urls_count",
            new_name="new_listings_count",
        ),
        migrations.RenameIndex(  # ty: ignore[unresolved-attribute]
            model_name="listing",
            new_name="idx_listings_website",
            old_name="idx_listing_urls_website",
        ),
        migrations.AlterModelTable(
            name="listing",
            table="listings",
        ),
    ]
