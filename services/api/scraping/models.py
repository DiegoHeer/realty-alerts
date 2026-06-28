from django.db import models
from django.db.models.functions import Cast, NullIf


class Website(models.TextChoices):
    FUNDA = "funda", "Funda"
    PARARIUS = "pararius", "Pararius"
    VASTGOED_NL = "vastgoed_nl", "VastgoedNL"


class ListingStatus(models.TextChoices):
    NEW = "new", "Nieuw"
    SALE_PENDING = "sale_pending", "Verkocht onder voorbehoud"
    SOLD = "sold", "Verkocht"


class ListScrapeRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class DetailScrapeRunStatus(models.TextChoices):
    DISPATCHED = "DISPATCHED", "Dispatched"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"


class BagStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"
    PARSE_FAILED = "parse_failed", "Parse failed"
    MISSING_ADDRESS = "missing_address", "Missing address"
    BAG_NO_MATCH = "bag_no_match", "BAG no match"
    BAG_AMBIGUOUS = "bag_ambiguous", "BAG ambiguous"


class BuildingType(models.TextChoices):
    APARTMENT = "apartment", "Appartement"
    TERRACED = "terraced", "Tussenwoning"
    CORNER = "corner", "Hoekwoning"
    SEMI_DETACHED = "semi_detached", "Twee-onder-één-kap"
    DETACHED = "detached", "Vrijstaand"


class ConstructionType(models.TextChoices):
    NIEUWBOUW = "nieuwbouw", "Nieuwbouw"
    BESTAANDE_BOUW = "bestaande_bouw", "Bestaande bouw"


class EnergyLabel(models.TextChoices):
    A5PLUS = "A+++++", "A+++++"
    A4PLUS = "A++++", "A++++"
    A3PLUS = "A+++", "A+++"
    A2PLUS = "A++", "A++"
    A1PLUS = "A+", "A+"
    A = "A", "A"
    B = "B", "B"
    C = "C", "C"
    D = "D", "D"
    E = "E", "E"
    F = "F", "F"
    G = "G", "G"


class DealType(models.TextChoices):
    SALE = "sale", "Te koop"
    RENT = "rent", "Te huur"


class Residence(models.Model):
    """One physical property, keyed on its BAG ID. Per-portal scraped data
    (price, title, image, status) lives on the child `Listing` rows; this
    model holds the BAG-canonical address plus reconciled aggregates that the
    matcher filters and orders on. `title` and `image_url` are computed from
    the freshest resolved Listing for display only."""

    bag_id = models.CharField(max_length=16, unique=True)
    city = models.CharField(max_length=255, db_index=True)
    street = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.PositiveIntegerField(null=True, blank=True)
    house_letter = models.CharField(max_length=5, null=True, blank=True)
    house_number_suffix = models.CharField(max_length=20, null=True, blank=True)
    postcode = models.CharField(max_length=10, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    neighbourhood = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    building_type = models.CharField(max_length=20, choices=BuildingType.choices, null=True, blank=True)
    energy_label = models.CharField(max_length=10, choices=EnergyLabel.choices, null=True, blank=True)
    energy_label_valid_until = models.DateField(null=True, blank=True)
    construction_type = models.CharField(max_length=20, choices=ConstructionType.choices, null=True, blank=True)
    zoning_designation = models.CharField(max_length=100, null=True, blank=True)
    zoning_fetched_at = models.DateTimeField(null=True, blank=True)
    soil_investigation_count = models.PositiveSmallIntegerField(null=True, blank=True)
    soil_contamination_status = models.CharField(max_length=100, null=True, blank=True)
    soil_investigation_outcome = models.CharField(max_length=100, null=True, blank=True)
    soil_fetched_at = models.DateTimeField(null=True, blank=True)
    foundation_risk_label = models.CharField(max_length=100, null=True, blank=True)
    foundation_risk_soil_type = models.CharField(max_length=100, null=True, blank=True)
    foundation_risk_pre1970_pct = models.FloatField(null=True, blank=True)
    foundation_risk_description = models.TextField(null=True, blank=True)
    foundation_risk_fetched_at = models.DateTimeField(null=True, blank=True)
    # Reconciled aggregates — recomputed by scraping.reconciliation.reconcile_residence
    # whenever a child Listing is created or updated. The matcher reads these.
    current_price_eur = models.BigIntegerField(null=True, blank=True)
    current_status = models.CharField(max_length=16, choices=ListingStatus.choices, default=ListingStatus.NEW)
    deal_type = models.CharField(max_length=10, choices=DealType.choices, default=DealType.SALE)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Denormalized from the freshest resolved Listing (see reconciliation).
    bedroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    bathroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    surface_area_m2 = models.PositiveIntegerField(null=True, blank=True)
    build_year = models.PositiveSmallIntegerField(null=True, blank=True)
    price_per_m2 = models.GeneratedField(
        expression=Cast("current_price_eur", output_field=models.FloatField())
        / NullIf("surface_area_m2", models.Value(0)),
        output_field=models.FloatField(),
        db_persist=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "residences"
        indexes = [
            models.Index(fields=["city", "current_price_eur"], name="idx_residences_filters"),
            models.Index(fields=["deal_type", "-created_at", "-id"], name="idx_res_dealtype_created"),
            models.Index(fields=["latitude", "longitude"], name="idx_res_lat_lon"),
            models.Index(fields=["building_type"], name="idx_res_building_type"),
            models.Index(fields=["energy_label"], name="idx_res_energy_label"),
            models.Index(fields=["bedroom_count"], name="idx_res_bedroom_count"),
            models.Index(fields=["bathroom_count"], name="idx_res_bathroom_count"),
            models.Index(fields=["surface_area_m2"], name="idx_res_surface_area"),
            models.Index(fields=["build_year"], name="idx_res_build_year"),
            models.Index(fields=["price_per_m2"], name="idx_res_price_per_m2"),
        ]

    def __str__(self) -> str:
        return f"{self.title or '(no title)'} ({self.city})"

    def _freshest_resolved_listing(self) -> Listing | None:
        return (
            Listing.objects.filter(residence=self, bag_status=BagStatus.RESOLVED).order_by("-list_scraped_at").first()
        )

    @property
    def title(self) -> str | None:
        listing = self._freshest_resolved_listing()
        return listing.title if listing else None

    @property
    def image_url(self) -> str | None:
        listing = self._freshest_resolved_listing()
        return listing.image_url if listing else None


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
    list_scraped_at = models.DateTimeField(null=True, blank=True)
    detail_scraped_at = models.DateTimeField(null=True, blank=True)
    surface_area_m2 = models.PositiveIntegerField(null=True, blank=True)
    bedroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    bathroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    room_count = models.PositiveSmallIntegerField(null=True, blank=True)
    construction_period = models.CharField(max_length=50, null=True, blank=True)
    energy_label = models.CharField(max_length=10, null=True, blank=True)
    building_type = models.CharField(max_length=20, choices=BuildingType.choices, null=True, blank=True)
    construction_type = models.CharField(max_length=20, choices=ConstructionType.choices, null=True, blank=True)
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


class ListScrapeRun(models.Model):
    website = models.CharField(max_length=20, choices=Website.choices)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ListScrapeRunStatus.choices)
    listings_found = models.PositiveIntegerField(default=0)
    new_listings_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "list_scrape_runs"
        indexes = [
            models.Index(fields=["website", "started_at"], name="idx_list_scrape_runs_started"),
        ]

    def __str__(self) -> str:
        return f"{self.website} {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"


class DetailScrapeRun(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="detail_scrape_runs")
    website = models.CharField(max_length=20, choices=Website.choices)
    status = models.CharField(max_length=12, choices=DetailScrapeRunStatus.choices)
    dispatched_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "detail_scrape_runs"
        indexes = [
            models.Index(fields=["listing", "dispatched_at"], name="idx_detail_runs_dispatched"),
        ]

    def __str__(self) -> str:
        return f"Detail {self.website} {self.status} listing={self.listing.pk} @ {self.dispatched_at:%Y-%m-%d %H:%M}"


class City(models.Model):
    code = models.CharField(max_length=6, unique=True)
    name = models.CharField(max_length=255)
    geometry = models.JSONField(null=True, blank=True)
    stats = models.JSONField(null=True, blank=True)
    stats_year = models.PositiveSmallIntegerField(null=True, blank=True)
    geometry_fetched_at = models.DateTimeField(null=True, blank=True)
    stats_fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cities"
        verbose_name_plural = "cities"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class District(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="districts")
    geometry = models.JSONField(null=True, blank=True)
    stats = models.JSONField(null=True, blank=True)
    stats_year = models.PositiveSmallIntegerField(null=True, blank=True)
    geometry_fetched_at = models.DateTimeField(null=True, blank=True)
    stats_fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "districts"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Neighborhood(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=255)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="neighborhoods")
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="neighborhoods", null=True, blank=True
    )
    geometry = models.JSONField(null=True, blank=True)
    stats = models.JSONField(null=True, blank=True)
    stats_year = models.PositiveSmallIntegerField(null=True, blank=True)
    geometry_fetched_at = models.DateTimeField(null=True, blank=True)
    stats_fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "neighborhoods"

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
