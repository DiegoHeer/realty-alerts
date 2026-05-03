from django.db import models


class Website(models.TextChoices):
    FUNDA = "funda", "Funda"
    PARARIUS = "pararius", "Pararius"
    VASTGOED_NL = "vastgoed_nl", "VastgoedNL"


class ListingStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ScrapeRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class DeadListingReason(models.TextChoices):
    PARSE_FAILED = "parse_failed", "Parse failed"
    MISSING_POSTCODE_AND_STREET = "missing_postcode_and_street", "Missing postcode and street"
    BAG_NO_MATCH = "bag_no_match", "BAG no match"
    BAG_AMBIGUOUS = "bag_ambiguous", "BAG ambiguous"


class Listing(models.Model):
    website = models.CharField(max_length=20, choices=Website.choices)
    detail_url = models.URLField(max_length=500, unique=True)
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    price_eur = models.BigIntegerField(null=True, blank=True)
    city = models.CharField(max_length=255, db_index=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    bag_id = models.CharField(max_length=16, null=True, blank=True, db_index=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    bedrooms = models.PositiveIntegerField(null=True, blank=True)
    area_sqm = models.FloatField(null=True, blank=True)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=ListingStatus.choices,
        default=ListingStatus.ACTIVE,
    )
    scraped_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "listings"
        indexes = [
            models.Index(fields=["city", "property_type", "price_eur"], name="idx_listings_filters"),
            models.Index(fields=["website", "created_at"], name="idx_listings_website_created"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.city})"


class DeadListing(models.Model):
    """Listings that fail BAG enrichment terminally — bad input from the
    source (typo postcode, garbage address) or a BAG miss we can't recover.
    Kept separate from `listings` so notification/matching never sees them
    and they're easy to triage from /admin."""

    website = models.CharField(max_length=20, choices=Website.choices)
    detail_url = models.URLField(max_length=500, unique=True)
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    city = models.CharField(max_length=255)
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    reason = models.CharField(max_length=40, choices=DeadListingReason.choices)
    scraped_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dead_listings"
        indexes = [
            models.Index(fields=["website", "created_at"], name="idx_dead_listings_website"),
            models.Index(fields=["reason", "created_at"], name="idx_dead_listings_reason"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.reason})"


class ScrapeRun(models.Model):
    website = models.CharField(max_length=20, choices=Website.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ScrapeRunStatus.choices)
    listings_found = models.PositiveIntegerField(default=0)
    listings_new = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "scrape_runs"
        indexes = [
            models.Index(fields=["website", "started_at"], name="idx_scrape_runs_started"),
        ]

    def __str__(self) -> str:
        return f"{self.website} {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"
