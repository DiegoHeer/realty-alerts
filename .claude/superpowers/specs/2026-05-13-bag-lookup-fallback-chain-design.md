# BAG Lookup Fallback Chain

**Date:** 2026-05-13
**Status:** Design approved
**Scope:** `services/api/scraping/`

## Problem

BAG enrichment fails when scraped address data contains errors:

1. **Wrong postcode letter** (e.g. `2613GG` instead of `2613GH`): the postcode query path fails, but the street+city fallback is never tried because the postcode field is present (not `None`).
2. **Abbreviated/misspelled street names** (e.g. "Corn. de Wittstraat" instead of "Cornelis de Wittstraat"): the Kadaster API requires exact street name matches.

With more scrapers planned, address data quality will vary. The lookup system needs a robust, extensible fallback chain.

## API Capabilities (Tested 2026-05-13)

| API | Exact match | Fuzzy match | Case-insensitive | Free-text | Auth |
|-----|-------------|-------------|------------------|-----------|------|
| Kadaster Individuele Bevragingen v2 | Yes | No | Yes | No (`zoek` returns 400) | API key |
| PDOK Locatieserver v3.1 | Yes | Yes (Solr) | Yes | Yes (`suggest`) | None |

**PDOK caveats:**
- Including a wrong postcode in the query poisons results (0 hits)
- Availability can be spotty (500 errors observed during testing — Solr overload)
- `/suggest` returns a candidate ID; `/lookup` returns full details including `nummeraanduiding_id` (BAG ID)

## Architecture: Strategy/Resolver Chain

Replace the monolithic `BagClient.lookup()` with a chain of `AddressResolver` implementations. Each resolver attempts one lookup strategy and either succeeds or passes to the next.

### Fallback Chain

```
1. KadasterPostcodeResolver    — postcode + huisnummer
   ↳ wrapped in RetryWithoutSpecifics
2. KadasterStreetCityResolver  — street + city + huisnummer
   ↳ wrapped in RetryWithoutSpecifics
3. PdokFuzzyResolver           — PDOK Locatieserver fuzzy search
```

Step 1 is the fastest and most reliable path. Step 2 catches wrong-postcode scenarios. Step 3 catches abbreviated/misspelled street names via PDOK's Solr-based fuzzy matching.

### Core Types

**`AddressQuery`** — frozen dataclass bundling lookup parameters:
- `postcode`, `house_number`, `house_letter`, `house_number_suffix`, `street`, `city`
- `without_specifics()` method returns a copy without `house_letter` and `house_number_suffix`

**`AddressResolver`** — Protocol:
```python
class AddressResolver(Protocol):
    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        """BagLookupSuccess on match, BagLookupFailure on definitive miss, None to pass."""
        ...
```

`None` means "I cannot help with this query, try the next resolver."
`BagLookupFailure` means "I tried and found a definitive outcome."
`BagLookupSuccess` means "Resolved — stop the chain."

**`BagLookupSuccess`**, **`BagLookupFailure`**, **`BagLookupResult`** — unchanged from current codebase.

### ChainedResolver

Orchestrates the chain. Public entry point for callers.

- **Pre-check**: returns `MISSING_ADDRESS` immediately when `house_number` is `None` or when neither postcode nor street+city are available
- **Iteration**: calls each resolver in order; stops at first `BagLookupSuccess`
- **Failure tracking**: remembers the most specific failure encountered (`AMBIGUOUS` > `NO_MATCH`) so admin diagnostic info is preserved
- **Error propagation**: does NOT catch `httpx.HTTPError` — lets Kadaster transport errors propagate to Celery for retry. Only `PdokFuzzyResolver` swallows its own errors.
- **Context manager**: `__exit__` calls `close()` on each resolver that implements it

### RetryWithoutSpecifics (Decorator Resolver)

Wraps any `AddressResolver`. If the inner resolver returns `None` and the query includes `house_letter` or `house_number_suffix`, retries with `query.without_specifics()`.

Applied to both Kadaster resolvers:
```python
ChainedResolver([
    RetryWithoutSpecifics(KadasterPostcodeResolver(config)),
    RetryWithoutSpecifics(KadasterStreetCityResolver(config)),
    PdokFuzzyResolver(),
])
```

If the retry produces `AMBIGUOUS`, the wrapper returns `None` (can't uniquely resolve with relaxed constraints) so the chain continues to the next resolver.

### KadasterPostcodeResolver

- Requires `postcode` and `house_number`; returns `None` when either is missing
- Queries `GET /adressen?postcode=NNNNAA&huisnummer=N` (+ optional `huisletter`, `huisnummertoevoeging`)
- Normalizes postcode: strips whitespace, uppercases
- Uses shared `resolve_addresses()` for disambiguation when multiple results come back
- 5xx → `httpx.HTTPStatusError` propagates (Celery retries)
- 404 or empty results → returns `None`
- Owns its own `httpx.Client` constructed from `KadasterConfig`

### KadasterStreetCityResolver

- Requires `street`, `city`, and `house_number`; returns `None` when any is missing
- Queries `GET /adressen?openbareRuimteNaam=X&woonplaatsNaam=Y&huisnummer=N` (+ optional letter/suffix)
- Uses same shared `resolve_addresses()` for disambiguation
- Same error propagation as postcode resolver
- Owns its own `httpx.Client` constructed from `KadasterConfig`

### KadasterConfig

Frozen dataclass shared by both Kadaster resolvers:
- `api_key: str`
- `base_url: str = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"`
- `timeout: float = 10.0`

### resolve_addresses() — Shared Disambiguation

Extracted from current `BagClient._resolve()`. Standalone function in `kadaster.py`:
```python
def resolve_addresses(
    addresses: list[dict],
    *,
    house_letter: str | None,
    house_number_suffix: str | None,
) -> BagLookupSuccess | BagLookupFailure:
```

When multiple results come back, filters by exact match on `house_letter` and `house_number_suffix`. Returns `AMBIGUOUS` if 0 or 2+ matches remain after filtering.

### PdokFuzzyResolver

Last-resort resolver using the PDOK Locatieserver's Solr-based fuzzy matching.

**Two-step lookup:**
1. `GET /suggest?q={street}+{house_number}+{city}&fq=type:adres&rows=1` — returns candidate `id` + `score`
2. `GET /lookup?id={id}&fl=nummeraanduiding_id,straatnaam,huisnummer,huisletter,huisnummertoevoeging,postcode,woonplaatsnaam` — returns full address details

**Query construction:** `"{street} {house_number} {city}"` — deliberately omits postcode (a wrong postcode poisons PDOK results, confirmed by live testing). House letter/suffix also omitted for cleaner fuzzy matching.

**Minimum score threshold:** configurable constant `_MIN_SCORE = 10.0` — rejects low-confidence matches to avoid false positives. Based on tested score of 12.35 for an abbreviated match.

**Error handling:** all errors (`httpx.HTTPError`, `ValueError`, `KeyError`, timeout) caught and logged via loguru, returns `None`. PDOK flakiness never blocks the pipeline or triggers Celery retry.

**Result construction:** builds `BagLookupSuccess` directly from PDOK `/lookup` response. The `nummeraanduiding_id` field is the BAG ID. No Kadaster round-trip needed.

Owns its own `httpx.Client` with a separate base URL and timeout.

### Factory Function

```python
def create_resolver(*, api_key: str, base_url: str = _BAG_BASE_URL, timeout: float = 10.0) -> ChainedResolver:
    """Wire up the full BAG resolution chain."""
```

Constructs `KadasterConfig`, all resolvers, wraps Kadaster resolvers in `RetryWithoutSpecifics`, returns a `ChainedResolver`. Callers use it as a context manager.

## File Plan

Resolver logic lives in a `scraping/resolvers/` package:

```
scraping/resolvers/
  __init__.py     — re-exports public API
  types.py        — AddressQuery, AddressResolver protocol, BagLookupSuccess/Failure/Result
  chain.py        — ChainedResolver, RetryWithoutSpecifics, create_resolver()
  kadaster.py     — KadasterConfig, KadasterPostcodeResolver, KadasterStreetCityResolver, resolve_addresses()
  pdok.py         — PdokFuzzyResolver
```

| File | Action |
|------|--------|
| `scraping/resolvers/__init__.py` | New — re-exports public API |
| `scraping/resolvers/types.py` | New — types (moved from `bag_client.py`) |
| `scraping/resolvers/chain.py` | New — chain + factory |
| `scraping/resolvers/kadaster.py` | New — Kadaster resolvers |
| `scraping/resolvers/pdok.py` | New — PDOK resolver |
| `scraping/bag_client.py` | Delete — replaced by `scraping/resolvers/` |
| `scraping/tasks.py` | Update — import from `scraping.resolvers` |
| `scraping/admin.py` | Update — import from `scraping.resolvers` |
| `tests/test_bag_client.py` | Delete — split into resolver-specific files |
| `tests/test_resolvers_chain.py` | New — chain + decorator tests with mock resolvers |
| `tests/test_resolvers_kadaster.py` | New — Kadaster resolver unit tests with `respx` |
| `tests/test_resolvers_pdok.py` | New — PDOK resolver unit tests with `respx` |
| `tests/test_tasks.py` | Update — adjusted for resolver chain construction |

## Caller Changes

```python
# Before
with BagClient(api_key=settings.BAG_API_KEY) as client:
    result = client.lookup(postcode=..., house_number=..., ...)

# After
with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
    result = resolver.resolve(AddressQuery(postcode=..., house_number=..., ...))
```

Return type (`BagLookupResult`) is unchanged. All downstream handling in `tasks.py` and `admin.py` stays the same.

## Error Handling Summary

| Source | Error | Behavior |
|--------|-------|----------|
| Kadaster 5xx | `httpx.HTTPStatusError` | Propagates → Celery retries (max 5, 300s backoff) |
| Kadaster 404 / empty | — | Resolver returns `None`, chain continues |
| PDOK any error | any exception | Caught + logged, resolver returns `None` |
| Missing `house_number` | — | `ChainedResolver` short-circuits with `MISSING_ADDRESS` |
| No postcode AND no street+city | — | `ChainedResolver` short-circuits with `MISSING_ADDRESS` |
| All resolvers pass | — | Most specific failure seen: `AMBIGUOUS` > `NO_MATCH` |

## Testing Strategy

- **Per-resolver unit tests**: each resolver tested in isolation with `respx` mocking its target API
- **Chain tests**: mock `AddressResolver` implementations verify chain iteration, failure tracking, MISSING_ADDRESS short-circuit, and context manager lifecycle
- **RetryWithoutSpecifics tests**: wrap a mock resolver, verify retry triggers on letter/suffix, not otherwise
- **Integration**: `test_tasks.py` verifies `resolve_bag` constructs and uses the chain correctly
- **Migration**: all 24 existing `test_bag_client.py` scenarios migrated to `test_resolvers_kadaster.py` + `test_resolvers_chain.py`

## Verification

1. `make test` — all tests pass
2. `make pre-commit` — ruff + ty clean
3. Manual: "Cornelis de Wittstraat 46, postcode 2613GG, Delft" → resolves via step 2 (street+city)
4. Manual: "Corn. de Wittstraat 46, no postcode, Delft" → resolves via step 3 (PDOK)
