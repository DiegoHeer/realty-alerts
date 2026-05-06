from django.db import models


class Website(models.TextChoices):
    FUNDA = "funda", "Funda"
    PARARIUS = "pararius", "Pararius"
    VASTGOED_NL = "vastgoed_nl", "VastgoedNL"


class ListingStatus(models.TextChoices):
    NEW = "new", "Nieuw"
    SALE_PENDING = "sale_pending", "Verkocht onder voorbehoud"
    SOLD = "sold", "Verkocht"


class ScrapeRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class DeadResidenceReason(models.TextChoices):
    PARSE_FAILED = "parse_failed", "Parse failed"
    MISSING_POSTCODE_AND_STREET = "missing_postcode_and_street", "Missing postcode and street"
    BAG_NO_MATCH = "bag_no_match", "BAG no match"
    BAG_AMBIGUOUS = "bag_ambiguous", "BAG ambiguous"


class BagStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"
    PARSE_FAILED = "parse_failed", "Parse failed"
    MISSING_ADDRESS = "missing_address", "Missing address"
    BAG_NO_MATCH = "bag_no_match", "BAG no match"
    BAG_AMBIGUOUS = "bag_ambiguous", "BAG ambiguous"


class Residence(models.Model):
    """One row per physical property, keyed on its BAG ID. Per-portal listings
    live in `Listing` so the same property advertised on Funda + Pararius
    collapses to a single residence row. Status mirrors the portal's own badge
    (`Nieuw` / `Verkocht onder voorbehoud` / `Verkocht`) and updates on every
    scrape."""

    bag_id = models.CharField(max_length=16, unique=True)
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    price_eur = models.BigIntegerField(null=True, blank=True)
    city = models.CharField(max_length=255, db_index=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    property_type = models.CharField(max_length=100, null=True, blank=True)
    bedrooms = models.PositiveIntegerField(null=True, blank=True)
    area_sqm = models.FloatField(null=True, blank=True)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    status = models.CharField(max_length=16, choices=ListingStatus.choices, default=ListingStatus.NEW)
    status_changed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scraped_at = models.DateTimeField()
    # Reconciled aggregates — recomputed by scraping.reconciliation.reconcile_residence
    # whenever a child Listing is created or updated. The matcher reads these.
    current_price_eur = models.BigIntegerField(null=True, blank=True)
    current_status = models.CharField(max_length=16, choices=ListingStatus.choices, default=ListingStatus.NEW)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "residences"
        indexes = [
            models.Index(fields=["city", "property_type", "price_eur"], name="idx_residences_filters"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.city})"


class Listing(models.Model):
    """One row per portal advertisement. Multiple `Listing`s may point at the
    same `Residence` when the property is advertised across portals. Holds
    everything the portal said about the listing: per-portal price/title/image/
    status, the raw address bits used to look up the BAG record, and the BAG
    resolution state. `residence` is null until BAG resolution succeeds."""

    residence = models.ForeignKey(Residence, related_name="listings", on_delete=models.CASCADE, null=True, blank=True)
    website = models.CharField(max_length=20, choices=Website.choices)
    url = models.URLField(max_length=500, unique=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    # Per-portal scraped data
    title = models.CharField(max_length=500, null=True, blank=True)
    price = models.CharField(max_length=100, null=True, blank=True)
    price_eur = models.BigIntegerField(null=True, blank=True)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    status = models.CharField(max_length=16, choices=ListingStatus.choices, default=ListingStatus.NEW)
    scraped_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    # Raw address bits scraped from the portal — only what BAG needs to resolve
    # to an official record. Canonical address lives on Residence.
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    # BAG resolution lifecycle: pending → resolved | (parse_failed | missing_address |
    # bag_no_match | bag_ambiguous). Existing rows backfill to 'resolved'.
    bag_status = models.CharField(max_length=20, choices=BagStatus.choices, default=BagStatus.RESOLVED)
    bag_failure_reason = models.TextField(null=True, blank=True)
    bag_resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "listings"
        indexes = [
            models.Index(fields=["website", "first_seen_at"], name="idx_listings_website"),
            models.Index(fields=["bag_status"], name="idx_listings_bag_status"),
        ]

    def __str__(self) -> str:
        return f"{self.website}: {self.url}"


class DeadResidence(models.Model):
    """Residences that fail BAG enrichment terminally — bad input from the
    source (typo postcode, garbage address) or a BAG miss we can't recover.
    Kept separate from `residences` so notification/matching never sees them
    and they're easy to triage from /admin."""

    website = models.CharField(max_length=20, choices=Website.choices)
    detail_url = models.URLField(max_length=500, unique=True)
    bag_id = models.CharField(max_length=16, null=True, blank=True)
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    city = models.CharField(max_length=255)
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    reason = models.CharField(max_length=40, choices=DeadResidenceReason.choices)
    scraped_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dead_residences"
        indexes = [
            models.Index(fields=["website", "created_at"], name="idx_dead_residences_website"),
            models.Index(fields=["reason", "created_at"], name="idx_dead_residences_reason"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.reason})"

    @property
    def is_promotion_ready(self) -> bool:
        return not self.missing_promotion_fields

    @property
    def missing_promotion_fields(self) -> list[str]:
        return [
            name
            for name, value in (
                ("bag_id", self.bag_id),
                ("title", self.title),
                ("price", self.price),
                ("city", self.city),
            )
            if not value
        ]


class ScrapeRun(models.Model):
    website = models.CharField(max_length=20, choices=Website.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ScrapeRunStatus.choices)
    listings_found = models.PositiveIntegerField(default=0)
    new_residences_count = models.PositiveIntegerField(default=0)
    new_listings_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "scrape_runs"
        indexes = [
            models.Index(fields=["website", "started_at"], name="idx_scrape_runs_started"),
        ]

    def __str__(self) -> str:
        return f"{self.website} {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"
