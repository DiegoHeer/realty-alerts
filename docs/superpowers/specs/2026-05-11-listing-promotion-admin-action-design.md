# Listing Promotion Admin Action

## Context

After the listing-source-of-truth migration (May 7 2026), the separate `DeadListing` table was removed. All listings — resolved and failed — now live in the `Listing` table, distinguished by `bag_status`. Failed listings (`bag_no_match`, `bag_ambiguous`, `missing_address`, `parse_failed`) have `residence=NULL` and are invisible to the notification pipeline.

Previously, operators could manually correct address data on dead listings and bulk-promote them back into the live pipeline via a Django admin action. That capability was lost in the migration.

This spec restores the ability to manually correct and re-resolve failed listings from the Listing admin.

## Operator Workflow

1. Filter the Listing list view by **BAG status → Failed (any)**
2. Click into a failed listing, correct address fields (street, house_number, house_letter, house_number_suffix, postcode, city), save
3. Back in the list view, select one or more corrected listings via checkboxes
4. Pick **"Promote selected listings"** from the actions dropdown
5. See immediate per-listing feedback via Django messages

## Implementation

### `_promote_listing()` — private function in `admin.py`

```
_promote_listing(listing: Listing, client: BagClient) -> str | None
```

Accepts a `Listing` and a shared `BagClient` instance. Returns `None` on success, or an error message string on failure.

**Steps:**

1. **Guard**: if `listing.bag_status` not in `{PARSE_FAILED, MISSING_ADDRESS, BAG_NO_MATCH, BAG_AMBIGUOUS}` → return `"skipped — bag_status is {status}, not a failed state"`
2. **BAG lookup**: call `client.lookup()` with the listing's current address fields (`postcode`, `house_number`, `house_letter`, `house_number_suffix`, `street`, `city`)
3. **On `BagLookupFailure`**: update `listing.bag_failure_reason` with the new failure reason, save, return descriptive error
4. **On `BagLookupSuccess`**:
   - `Residence.objects.get_or_create(bag_id=result.bag_id, defaults={address fields from BAG result})` — if the Residence already exists, no address fields are overwritten (the BAG-canonical data from the first resolution is authoritative)
   - Set `listing.residence = residence`
   - Set `listing.bag_status = BagStatus.RESOLVED`
   - Set `listing.bag_resolved_at = timezone.now()`
   - Clear `listing.bag_failure_reason = ""`
   - Save listing
   - Call `reconcile_residence(residence)`
5. **On `httpx.HTTPError`**: return `"BAG API error — {error}"`

### `promote_listings` — admin action on `ListingAdmin`

```python
@admin.action(description="Promote selected listings")
def promote_listings(modeladmin, request, queryset):
```

- Opens a single `BagClient` context manager for the batch (one HTTP client, reused)
- Loops over `queryset`, calls `_promote_listing(listing, client)` for each
- Tracks success count and per-listing error messages
- After the loop:
  - If successes > 0: `modeladmin.message_user(request, f"Successfully promoted {n} listing(s).", messages.SUCCESS)`
  - For each failure: `modeladmin.message_user(request, f"Listing {id} ({url}): {reason}", messages.WARNING)`

Registered on `ListingAdmin` via `actions = [promote_listings]`.

### Scope guard

The action only processes listings with a terminal-failed `bag_status`. Listings that are `RESOLVED` or `PENDING` are skipped with a warning message. This prevents accidentally re-resolving already-linked listings.

### Failed BAG statuses (constant)

Define a module-level frozenset for reuse by both the filter and the promotion guard:

```python
_FAILED_BAG_STATUSES = frozenset({
    BagStatus.PARSE_FAILED,
    BagStatus.MISSING_ADDRESS,
    BagStatus.BAG_NO_MATCH,
    BagStatus.BAG_AMBIGUOUS,
})
```

Use this in `BagStatusListFilter.queryset` (replacing the inline tuple) and in `_promote_listing`'s guard.

## Error messages

| Scenario | Level | Message |
|---|---|---|
| Not in failed state | WARNING | `Listing {id} ({url}): skipped — bag_status is {status}, not a failed state` |
| BAG: missing address | WARNING | `Listing {id} ({url}): still missing required address fields` |
| BAG: no match | WARNING | `Listing {id} ({url}): BAG lookup found no match for the corrected address` |
| BAG: ambiguous | WARNING | `Listing {id} ({url}): BAG lookup still returned multiple ambiguous results` |
| BAG API HTTP error | WARNING | `Listing {id} ({url}): BAG API error — {detail}` |
| Success (summary) | SUCCESS | `Successfully promoted {n} listing(s).` |

## Files to modify

- `services/api/scraping/admin.py` — add `_FAILED_BAG_STATUSES`, `_promote_listing()`, `promote_listings` action, update `ListingAdmin.actions`, refactor `BagStatusListFilter` to use the shared constant
- `services/api/tests/test_listing_promotion.py` — new test file

## Verification

1. Run `make test` — all existing tests pass, new promotion tests pass
2. Run `make pre-commit` — linting, formatting, type checks pass
3. Manual smoke test via Django admin:
   - Create or find a listing with `bag_status=bag_no_match`
   - Edit address fields to a known-valid Dutch address
   - Select listing, run "Promote selected listings" action
   - Verify: listing is now `RESOLVED`, linked to a Residence, success message shown
   - Try promoting an already-resolved listing — verify it's skipped with a warning
   - Try promoting a listing with still-bad address — verify failure message
