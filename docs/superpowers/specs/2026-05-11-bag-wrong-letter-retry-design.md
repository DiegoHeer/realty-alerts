# BAG Wrong-Letter Retry Design

**Date:** 2026-05-11
**Status:** Approved

## Problem

`BagClient.lookup()` queries the Kadaster API with all available address fields including `house_letter` and `house_number_suffix`. If a scraper incorrectly parses a house letter (e.g. extracts "Z" from an ambiguous address string), the API returns 200 with 0 results. The client currently treats this as `NO_MATCH` and stops. The listing gets stuck with `bag_status=BAG_NO_MATCH` even though the bare address (no letter, no suffix) exists and is uniquely resolvable.

## Solution

When the API returns 0 results **and** a `house_letter` or `house_number_suffix` was provided, retry the lookup with both fields omitted. Apply the existing disambiguation logic (which already favours bare addresses) to the retry response. If the retry cannot resolve to a unique address, return `NO_MATCH`.

## Architecture

The change lives entirely in `BagClient.lookup()` in `services/api/scraping/bag_client.py`. No changes to `tasks.py`, models, schemas, or admin.

### Implementation

After the `if not addresses:` check, insert a single recursive self-call:

```python
if not addresses:
    if house_letter or house_number_suffix:
        result = self.lookup(postcode=postcode, house_number=house_number)
        return BagLookupFailure.NO_MATCH if result is BagLookupFailure.AMBIGUOUS else result
    return BagLookupFailure.NO_MATCH
```

The recursive call passes `house_letter=None, house_number_suffix=None` (parameter defaults). Because both are `None`, the retry cannot trigger another retry — the recursion terminates after exactly one level.

The existing disambiguation block (added in PR #135) handles the retry response:
- 1 result → `BagLookupSuccess`
- 2+ results, exactly 1 bare (letter=None, suffix=None) → `BagLookupSuccess`
- 2+ results, 0 or 2+ bare → `AMBIGUOUS`, converted to `NO_MATCH` at the call site

### Behaviour table

| First call result | Letter/suffix given | Retry result | Final result |
|---|---|---|---|
| 0 results | Yes | 1 result | `BagLookupSuccess` |
| 0 results | Yes | bare + lettered → 1 bare | `BagLookupSuccess` |
| 0 results | Yes | all-suffixed → 0 bare | `NO_MATCH` |
| 0 results | Yes | 0 results | `NO_MATCH` |
| 0 results | No | — (no retry) | `NO_MATCH` |

### What does NOT change

- `AMBIGUOUS` status is never surfaced from the retry path (converted to `NO_MATCH`)
- Single-result responses are unaffected
- Multi-result responses that already disambiguate are unaffected
- `tasks.py` rate limit, retry policy, and status mapping are unchanged

## Testing

Five new tests in `services/api/tests/test_bag_client.py` using `respx` with a `side_effect` callback that returns different responses based on whether the request includes `huisletter`:

1. Wrong letter → retry picks bare address → `BagLookupSuccess`
2. Wrong suffix → retry picks bare address → `BagLookupSuccess`
3. No letter/suffix → 0 results → `NO_MATCH`, no retry (verify only 1 HTTP call made)
4. Wrong letter → retry also returns 0 → `NO_MATCH`
5. Wrong letter → retry finds only suffixed variants → `NO_MATCH`
