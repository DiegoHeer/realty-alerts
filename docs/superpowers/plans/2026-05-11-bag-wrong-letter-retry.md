# BAG Wrong-Letter Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a scraper sends an incorrect house letter or suffix and the Kadaster API returns 0 results, retry the lookup without those fields so the bare address can still be resolved.

**Architecture:** Single recursive call inside `BagClient.lookup()` — when 0 results and a letter/suffix was provided, re-call `self.lookup()` with only `postcode` and `house_number`. The existing disambiguation logic then picks the bare (letter=None, suffix=None) address if exactly one exists. If the retry returns `AMBIGUOUS` (no bare form), convert to `NO_MATCH` per product decision.

**Tech Stack:** Python 3.14, httpx, respx (test mocking)

---

## Files

| Action | Path | Purpose |
|---|---|---|
| Modify | `services/api/scraping/bag_client.py` | Add 4-line retry block after `if not addresses` |
| Modify | `services/api/tests/test_bag_client.py` | 5 new tests for retry scenarios |

---

### Task 1: Write 5 failing tests for the retry behaviour

**Files:**
- Modify: `services/api/tests/test_bag_client.py`

- [ ] **Step 1: Append the 5 new tests to the end of `test_bag_client.py`**

Add after the last existing test:

```python
# --- Wrong-letter/suffix retry tests ---
# When the API returns 0 results because the house_letter or house_number_suffix
# doesn't exist, the client must retry without those fields so the bare address
# can be resolved by the existing disambiguation logic.


@respx.mock
def test_lookup_retries_without_letter_when_letter_gives_no_results():
    """Wrong letter (e.g. 'Z') → 0 results → retry → bare address found."""
    def handler(request):
        if "huisletter" in str(request.url):
            return httpx.Response(200, json={"_embedded": {"adressen": []}})
        return httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
                    ]
                }
            },
        )

    respx.get(f"{_TEST_BASE_URL}/adressen").mock(side_effect=handler)

    with _client() as client:
        result = client.lookup(postcode="1506HC", house_number=10, house_letter="Z")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "001"
    assert result.house_letter is None


@respx.mock
def test_lookup_retries_without_suffix_when_suffix_gives_no_results():
    """Wrong suffix → 0 results → retry → bare address found."""
    def handler(request):
        if "huisnummertoevoeging" in str(request.url):
            return httpx.Response(200, json={"_embedded": {"adressen": []}})
        return httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="002", huisletter=None, huisnummertoevoeging="99"),
                    ]
                }
            },
        )

    respx.get(f"{_TEST_BASE_URL}/adressen").mock(side_effect=handler)

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9, house_number_suffix="WRONG")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "001"
    assert result.house_number_suffix is None


@respx.mock
def test_lookup_does_not_retry_when_no_letter_or_suffix_given():
    """No letter/suffix in input → 0 results → NO_MATCH with exactly 1 API call (no retry)."""
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": []}})
    )

    with _client() as client:
        result = client.lookup(postcode="9999XX", house_number=1)

    assert result is BagLookupFailure.NO_MATCH
    assert route.call_count == 1


@respx.mock
def test_lookup_returns_no_match_when_retry_also_finds_nothing():
    """Wrong letter → retry also returns 0 results → NO_MATCH."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": []}})
    )

    with _client() as client:
        result = client.lookup(postcode="9999XX", house_number=1, house_letter="A")

    assert result is BagLookupFailure.NO_MATCH


@respx.mock
def test_lookup_returns_no_match_when_retry_finds_no_bare_address():
    """Wrong letter → retry finds only suffixed variants (no bare address) → NO_MATCH."""
    def handler(request):
        if "huisletter" in str(request.url):
            return httpx.Response(200, json={"_embedded": {"adressen": []}})
        return httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging="1"),
                        _address(nummeraanduidingIdentificatie="002", huisletter=None, huisnummertoevoeging="2"),
                    ]
                }
            },
        )

    respx.get(f"{_TEST_BASE_URL}/adressen").mock(side_effect=handler)

    with _client() as client:
        result = client.lookup(postcode="1015BA", house_number=1, house_letter="Z")

    assert result is BagLookupFailure.NO_MATCH
```

- [ ] **Step 2: Run the new tests to confirm they all FAIL**

```bash
cd services/api && uv run pytest tests/test_bag_client.py -v -k "retry or no_letter_or_suffix or no_bare"
```

Expected: 5 failures. Each should fail because the client returns `BagLookupFailure.NO_MATCH` or `BagLookupFailure.AMBIGUOUS` instead of the expected value. If any test passes immediately, the test is wrong — fix it before continuing.

---

### Task 2: Implement the retry in `BagClient.lookup()`

**Files:**
- Modify: `services/api/scraping/bag_client.py:80-84`

- [ ] **Step 1: Read the current `if not addresses` block**

It currently looks like this (around line 80):

```python
        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return BagLookupFailure.NO_MATCH
        if len(addresses) > 1:
```

- [ ] **Step 2: Replace `if not addresses` with the retry block**

```python
        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            if house_letter or house_number_suffix:
                result = self.lookup(postcode=postcode, house_number=house_number)
                return BagLookupFailure.NO_MATCH if result is BagLookupFailure.AMBIGUOUS else result
            return BagLookupFailure.NO_MATCH
        if len(addresses) > 1:
```

The recursive call passes `house_letter=None, house_number_suffix=None` (parameter defaults), so it cannot trigger a second retry — recursion terminates after exactly one level.

- [ ] **Step 3: Run the full `test_bag_client.py` suite to confirm all 20 tests pass**

```bash
cd services/api && uv run pytest tests/test_bag_client.py -v
```

Expected output (last line):
```
20 passed in 0.Xs
```

If any existing test fails, the change broke something — revert the edit and re-examine.

- [ ] **Step 4: Run the full API test suite to confirm no regressions**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all tests pass (111 + 5 new = 116 total).

- [ ] **Step 5: Run pre-commit checks**

```bash
cd /path/to/worktree && make pre-commit
```

Expected: all Python hooks pass (ruff lint, ruff format, ty typecheck). The TS eslint hooks will fail due to missing `node_modules` in this environment — that is pre-existing and unrelated to this change.

- [ ] **Step 6: Commit**

```bash
git add services/api/scraping/bag_client.py services/api/tests/test_bag_client.py
git commit -m "fix(api): retry BAG lookup without letter/suffix when initial query returns nothing"
```

---

## Verification

After committing, confirm end-to-end behaviour matches the spec:

| Scenario | Expected |
|---|---|
| `huisletter="Z"` → 0 → retry → bare + lettered → disambiguation → bare | `BagLookupSuccess(house_letter=None)` |
| `house_number_suffix="WRONG"` → 0 → retry → bare + other suffix | `BagLookupSuccess(house_number_suffix=None)` |
| No letter/suffix → 0 results | `NO_MATCH`, exactly 1 HTTP call |
| Wrong letter → retry also 0 | `NO_MATCH` |
| Wrong letter → retry finds only suffixed variants | `NO_MATCH` |
