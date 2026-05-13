---
name: new-scraper
description: Scaffold a complete scraper for a new Dutch real estate portal. Analyzes the target site with Playwright MCP, generates a BaseScraper subclass with list + detail scraping, test fixtures, and registration wiring. Invoke when adding a new property website to services/scraper/.
---

# New Scraper Skill

Generate a complete scraper for a new Dutch real estate portal website. This skill uses Playwright MCP to analyze the target site's DOM structure, then generates production-ready code matching the existing scraper architecture.

## Prerequisites

- Playwright MCP server must be available (browser automation tools like `mcp__playwright__browser_navigate`, `mcp__playwright__browser_snapshot`, etc.)
- The target website must be a Dutch real estate listing portal

## Input

The user provides:
1. **URL** — homepage or listing search results page of the target portal
2. **Scraper name** — asked during the skill (e.g., `housing_nl`)

The scraper name determines all generated identifiers:
- Class: `{PascalCase}Scraper` (e.g., `HousingNLScraper`)
- File: `services/scraper/src/scraper/scrapers/{name}.py`
- Enum: `Website.{UPPER_SNAKE}` (e.g., `Website.HOUSING_NL`)
- Test: `services/scraper/tests/scrapers/test_{name}.py`

## Workflow

Follow these steps in order. Each step produces findings that feed into later steps. Track all discovered selectors, URLs, and patterns — they are used in the code generation step.

### Step 1: Collect scraper name

Ask the user for a scraper name (snake_case, e.g. `housing_nl`). This name is used for all generated filenames, class names, and enum values. Confirm the derived identifiers:

```
Name: housing_nl
Class: HousingNLScraper
Enum: Website.HOUSING_NL
File: scrapers/housing_nl.py
```

### Step 2: Navigate to the URL and detect page type

Navigate to the user-provided URL using Playwright:

```
mcp__playwright__browser_navigate(url=<user_url>)
mcp__playwright__browser_snapshot()
```

**Dismiss cookie consent if present:**
- Check the snapshot for cookie consent overlays (common selectors: buttons with text "Accepteren", "Akkoord", "Accept all", or elements matching `[id*="cookie"]` / `[class*="consent"]`)
- If found, click the accept/dismiss button:
  ```
  mcp__playwright__browser_click(element="Accept cookies button")
  ```
- Re-take the snapshot after dismissal:
  ```
  mcp__playwright__browser_snapshot()
  ```

**Determine if this is a listing search page:**
- Look for repeated card-like elements in the snapshot (groups of sibling elements each containing a link, price text with `€`, and optionally an image)
- If cards are found → this is the listing page. Record the URL as `LISTING_URL`. Proceed to Step 3.
- If no cards found → this is likely a homepage or other page. Ask the user: *"This doesn't look like a listing search page — I don't see repeated property cards. Can you provide the URL of the search results page?"* Then navigate to the new URL and re-check.

### Step 3: HTTP vs Playwright comparison

Compare plain HTTP fetch against the Playwright-rendered page to determine fetch strategy and detect bot markers.

**Fetch with plain HTTP using Bash:**

```bash
curl -s -o /tmp/http_response.html \
  -w "%{http_code}" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7" \
  "<LISTING_URL>"
```

**Get the Playwright-rendered HTML:**

```
mcp__playwright__browser_evaluate(expression="document.querySelectorAll('<CARD_SELECTOR>').length")
```

Also count the cards in the HTTP response (read `/tmp/http_response.html` and grep/count the card selector pattern).

**Compare and decide:**

| Outcome | Fetch strategy | Action |
|---|---|---|
| HTTP status != 200, or request fails | `PlaywrightFetch` | Set `fetch_strategy = "playwright"`, `detection_markers = ()` |
| HTTP 200 but card count differs significantly (HTTP has 0 or far fewer cards) | `PlaywrightFetch` | Set `fetch_strategy = "playwright"`. Inspect the HTTP response for block page markers (short page, CAPTCHA keywords like "verify", "robot", "blocked", or Dutch equivalents). Extract any found as `detection_markers`. |
| HTTP 200 and similar card count | `HttpFetch` | Set `fetch_strategy = "http"`, `detection_markers = ()` |

**Present finding to user:**
> "Plain HTTP returns [X] cards vs Playwright's [Y] cards. This site [needs Playwright / works with plain HTTP]. Detected block markers: [list or none]. Confirm?"

Record: `FETCH_STRATEGY`, `DETECTION_MARKERS`

### Step 4: Analyze listing page cards

With the listing page loaded in Playwright, analyze the card structure.

**4a. Identify card selector:**

Take a snapshot and examine the repeated card elements. Look for:
- `<section>`, `<article>`, `<div>`, or `<li>` elements with a shared CSS class that repeat for each listing
- Each card should contain: a link (`<a>` with href), price text, and typically an image

Record: `CARD_SELECTOR` (e.g., `section.listing-card`, `a.propertyLink`, `div[data-testid="listing"]`)

Use `browser_evaluate` to verify the count:
```
mcp__playwright__browser_evaluate(expression="document.querySelectorAll('<CARD_SELECTOR>').length")
```

**4b. Extract per-card field selectors:**

For each field, examine the first card's DOM structure. Use `browser_evaluate` to test selectors:

```
mcp__playwright__browser_evaluate(expression=`
  const card = document.querySelector('<CARD_SELECTOR>');
  JSON.stringify({
    links: [...card.querySelectorAll('a')].map(a => ({href: a.href, text: a.textContent.trim()})),
    prices: [...card.querySelectorAll('*')].filter(el => el.textContent.includes('€') && el.children.length === 0).map(el => ({tag: el.tagName, class: el.className, text: el.textContent.trim()})),
    images: [...card.querySelectorAll('img')].map(img => ({src: img.src, class: img.className})),
    headings: [...card.querySelectorAll('h1,h2,h3,h4,h5,h6,span,strong')].map(el => ({tag: el.tagName, class: el.className, text: el.textContent.trim()})).slice(0, 20)
  })
`)
```

From the results, identify selectors for:

| Field | What to look for |
|---|---|
| `detail_url` | The primary `<a>` link pointing to a detail page (href contains a path, not `#` or `javascript:`) |
| `title` | Heading or prominent text element — typically the street + house number |
| `price` | Element containing `€` + digits |
| `address` | Text containing street name + number. Often same as title, or a subtitle element. Will be parsed by `parse_dutch_address()` |
| `city` | Separate element with city name, or part of a subtitle with postcode |
| `postcode` | Text matching `\d{4}\s?[A-Z]{2}` — may be in subtitle, address line, or absent from cards |
| `image_url` | `<img>` `src` attribute |
| `status` | Badge/label with "verkocht", "onder voorbehoud" — handled by `detect_status()` on the card Tag |

**Present findings to user:**
> "Cards use `<CARD_SELECTOR>`. Fields I found:
> - detail_url: `a.card-link` → href
> - title: `h2.card-title` → text
> - price: `span.price` → text
> - address: from title text, parsed via `parse_dutch_address()`
> - city: `span.city` → text
> - postcode: found in subtitle / not found on cards
> - image: `img.card-image` → src
> - status: handled by `detect_status()` on card element
>
> Does this look right? Any corrections?"

Record all confirmed selectors as `CARD_FIELDS`.

**4c. Detect pagination:**

Look for pagination elements in the snapshot:

```
mcp__playwright__browser_evaluate(expression=`
  JSON.stringify({
    numbered_links: [...document.querySelectorAll('a')].filter(a => /^\\d+$/.test(a.textContent.trim())).map(a => ({text: a.textContent.trim(), href: a.href, parent_class: a.parentElement?.className})).slice(0, 10),
    next_buttons: [...document.querySelectorAll('a, button')].filter(el => /next|volgende|›|»|→/i.test(el.textContent.trim()) || el.getAttribute('aria-label')?.match(/next|volgende/i)).map(el => ({tag: el.tagName, text: el.textContent.trim(), href: el.href, class: el.className})),
    pagination_containers: [...document.querySelectorAll('[class*="pagination"], [class*="paging"], nav[aria-label*="pagination"]')].map(el => ({tag: el.tagName, class: el.className, html: el.innerHTML.slice(0, 500)}))
  })
`)
```

Determine pagination type:
- **Numbered links**: Extract URL pattern (query param like `?page=N`, path segment like `/page-N`)
- **Next button**: Extract the next-page URL pattern
- **None found**: Single page, no pagination loop needed

Record: `PAGINATION_TYPE` (numbered | next_button | none), `PAGINATION_URL_PATTERN`

Present finding to user:
> "Pagination: [type]. URL pattern: [pattern]. I'll generate a page loop capped at MAX_PAGES=5. Confirm?"

### Step 5: Analyze detail page

Navigate to one of the listing detail URLs found in Step 4:

```
mcp__playwright__browser_navigate(url=<first_detail_url>)
mcp__playwright__browser_snapshot()
```

If the page fails to load, try the next card's URL (up to 3 attempts).

**5a. Check for JSON-LD structured data:**

```
mcp__playwright__browser_evaluate(expression=`
  const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];
  scripts.map(s => { try { return JSON.parse(s.textContent) } catch { return null } }).filter(Boolean)
`)
```

If JSON-LD is found with address/property data, note which fields are available there (especially `postalCode`).

**5b. Extract detail field selectors:**

```
mcp__playwright__browser_evaluate(expression=`
  JSON.stringify({
    prices: [...document.querySelectorAll('*')].filter(el => el.textContent.includes('€') && el.children.length === 0 && el.textContent.trim().length < 50).map(el => ({tag: el.tagName, class: el.className, text: el.textContent.trim()})).slice(0, 5),
    dt_dd_pairs: [...document.querySelectorAll('dt')].map(dt => ({label: dt.textContent.trim(), value: dt.nextElementSibling?.textContent?.trim(), dd_class: dt.nextElementSibling?.className})).slice(0, 30),
    tables: [...document.querySelectorAll('th')].map(th => ({label: th.textContent.trim(), value: th.parentElement?.querySelector('td')?.textContent?.trim()})).slice(0, 30),
    labeled_spans: [...document.querySelectorAll('strong, label, .label')].map(el => ({text: el.textContent.trim(), next: el.nextElementSibling?.textContent?.trim(), next_class: el.nextElementSibling?.className})).filter(el => el.text.length < 50).slice(0, 30)
  })
`)
```

For each `DetailListing` field, find a selector:

| Field | Detection keywords in labels |
|---|---|
| `price` | Euro sign + digits, prominent element |
| `status` | "Status", or infer from price label |
| `surface_area_m2` | "woonoppervlakte", "wonen", "m²", "m2" |
| `bedroom_count` | "slaapkamer" |
| `bathroom_count` | "badkamer" |
| `room_count` | "kamers", "aantal kamers" |
| `construction_period` | "bouwjaar", "bouwperiode" |
| `energy_label` | "energielabel", "energie" |
| `postcode` | Dutch postcode pattern in address elements, or JSON-LD `postalCode` |

For fields that can't be found, ask the user:
> "I couldn't find `energy_label` on this page. Should I skip it (return `None`), or can you point me to it?"

Record all confirmed selectors as `DETAIL_FIELDS`.

### Step 6: Save test fixture HTML

Save the raw HTML from both pages as test fixtures. These are the same HTML files the Playwright/HTTP fetch captured during analysis.

**Save listing page HTML:**

```
mcp__playwright__browser_navigate(url=<LISTING_URL>)
mcp__playwright__browser_evaluate(expression="document.documentElement.outerHTML")
```

Write the output to `services/scraper/tests/data/{name}_listing.html`.

> **Note:** If the HTML output is too large for `browser_evaluate`, use `browser_evaluate` on a trimmed version (e.g., `document.body.outerHTML` wrapped in a minimal `<html>` shell), or use `browser_run_code_unsafe` to write the file to disk directly and then read it.

**Save detail page HTML:**

Navigate back to the detail page used in Step 5:

```
mcp__playwright__browser_navigate(url=<DETAIL_URL>)
mcp__playwright__browser_evaluate(expression="document.documentElement.outerHTML")
```

Write the output to `services/scraper/tests/data/{name}_detail.html`.

> **Note:** Same size caveat as above — use a trimmed version or `browser_run_code_unsafe` if the response is too large.

### Step 7: Generate scraper class

Create `services/scraper/src/scraper/scrapers/{name}.py` following the existing pattern. The generated code must:

**Imports** — follow the same import style as existing scrapers:

```python
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import ListingStatus, Website
from scraper.models import DetailListing, Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper
from scraper.status import detect_status
```

Add conditional imports only when needed (ruff will flag unused imports):
- `import re` — only if regex helpers like `_parse_first_int` are used
- `import json` — only if JSON-LD extraction is needed (for postcode)
- `from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse` — for query-param pagination
- `from pathlib import PurePosixPath` — for path-segment pagination

**Class structure:**

```python
class {PascalCase}Scraper(BaseScraper):
    website = Website.{UPPER_SNAKE}
    detection_markers = {DETECTION_MARKERS}  # tuple of strings, or ()
    MAX_PAGES = 5

    def __init__(self, fetch: FetchStrategy, base_url: str = "<LISTING_URL>") -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape_list(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping {DisplayName} (since={{since}})")
        last_page = self._get_last_page()
        listings: list[Listing] = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {{len(listings)}} listings across {{last_page}} pages")
        return listings

    def scrape_detail(self, url: str) -> DetailListing:
        soup = self.get_soup(url)
        return self._parse_detail_page(soup)
```

**Pagination** — use the pattern matching what was detected:

For **query param** pagination (like `?page=N` or `?p=N`):
```python
    def _get_last_page(self) -> int:
        soup = self.get_soup(self.base_url)
        # Adapt selector to match the pagination container found in Step 4c
        anchors = soup.select('<PAGINATION_SELECTOR>')
        page_numbers = [int(a.text) for a in anchors if a.text.isdigit()]
        max_page = max(page_numbers) if page_numbers else 1
        return min(max_page, self.MAX_PAGES)

    def _scrape_page(self, page_number: int) -> list[Listing]:
        page_url = self._append_page_number(self.base_url, page_number)
        soup = self.get_soup(page_url)
        cards = soup.select("<CARD_SELECTOR>")
        return [self._parse_card(card) for card in cards]

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["<PARAM_NAME>"] = [str(page_number)]
        new_query = urlencode(params, doseq=True, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))
```

For **path segment** pagination (like `/page-N`):
```python
    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        new_path = PurePosixPath(parsed.path) / f"page-{page_number}"
        return urlunparse(parsed._replace(path=str(new_path)))
```

**Card parsing** — adapt selectors from `CARD_FIELDS`:

```python
    def _parse_card(self, card: Tag) -> Listing:
        # detail_url
        url_el = card.select_one("<DETAIL_URL_SELECTOR>")
        detail_url = ...  # Extract href, prepend domain if relative

        # title
        title_el = card.select_one("<TITLE_SELECTOR>")
        title = title_el.get_text(strip=True) if title_el else ""

        # price
        price_el = card.select_one("<PRICE_SELECTOR>")
        price = price_el.get_text(strip=True) if price_el else ""

        # image
        image_el = card.select_one("<IMAGE_SELECTOR>")
        image_url = str(image_el.get("src", "")) if image_el else None

        # address from title or dedicated element
        street, house_number, house_letter, house_number_suffix = parse_dutch_address(title)

        # city — from subtitle or dedicated element
        city_el = card.select_one("<CITY_SELECTOR>")
        city = city_el.get_text(strip=True) if city_el else ""

        # postcode — from subtitle or None if not on card
        postcode = parse_dutch_postcode(<SUBTITLE_TEXT>) if <HAS_POSTCODE> else None

        return Listing(
            detail_url=detail_url,
            title=title,
            price=price,
            city=city,
            street=street,
            house_number=house_number,
            house_letter=house_letter,
            house_number_suffix=house_number_suffix,
            postcode=postcode,
            image_url=image_url,
            website=self.website,
            status=detect_status(card),
        )
```

**Detail page parsing** — adapt from `DETAIL_FIELDS`:

```python
    def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
        # price
        price_el = soup.select_one("<PRICE_SELECTOR>")
        price = price_el.get_text(strip=True) if price_el else ""

        # status
        status_text = <STATUS_EXTRACTION>  # dt/dd, badge, or infer from price
        status = _parse_status(status_text.lower() if status_text else "")

        # surface_area_m2, bedroom_count, etc. — use dt/dd, table, or dedicated selectors
        ...

        # postcode — JSON-LD or address element
        postcode = <POSTCODE_EXTRACTION>

        return DetailListing(
            price=price,
            status=status,
            surface_area_m2=surface_area_m2,
            bedroom_count=bedroom_count,
            bathroom_count=bathroom_count,
            room_count=room_count,
            construction_period=construction_period,
            energy_label=energy_label,
            postcode=postcode,
        )
```

**Private helper functions** — add at module level as needed, following existing patterns:

```python
def _parse_status(text: str) -> ListingStatus:
    if "voorbehoud" in text or "onder bod" in text:
        return ListingStatus.SALE_PENDING
    if "verkocht" in text:
        return ListingStatus.SOLD
    return ListingStatus.NEW
```

Add `_parse_first_int`, `_parse_dt_dd_text`, `_parse_json_ld_postcode` as needed — copy from existing scrapers (each scraper keeps its own private helpers, no shared module).

### Step 8: Register the scraper

**8a. Add enum value to `services/scraper/src/scraper/enums.py`:**

Add the new website to the `Website` enum, maintaining alphabetical order:

```python
class Website(StrEnum):
    FUNDA = "funda"
    # ... new entry in alphabetical position ...
    {UPPER_SNAKE} = "{name}"
    PARARIUS = "pararius"
    VASTGOED_NL = "vastgoed_nl"
```

**8b. Update `services/scraper/src/scraper/runner.py`:**

Add import:
```python
from scraper.scrapers.{name} import {PascalCase}Scraper
```

Add to `PORTAL_SCRAPER_MAP`:
```python
PORTAL_SCRAPER_MAP = {
    Website.FUNDA: FundaScraper,
    # ... new entry ...
    Website.{UPPER_SNAKE}: {PascalCase}Scraper,
    Website.PARARIUS: ParariusScraper,
    Website.VASTGOED_NL: VastgoedNLScraper,
}
```

Update `_make_fetch()` — add to the Playwright set if needed, or leave as-is for HttpFetch:

If `FETCH_STRATEGY == "playwright"`:
```python
if website in {Website.FUNDA, Website.PARARIUS, Website.{UPPER_SNAKE}}:
    return PlaywrightFetch(browser_url=browser_url)
```

If `FETCH_STRATEGY == "http"`: no change needed (the `else` branch already returns `HttpFetch()`).

### Step 9: Generate test file and update conftest

**9a. Add URL mappings to `services/scraper/tests/conftest.py`:**

Add to the `URL_TO_FILE` dict:
```python
    "<LISTING_URL>": "{name}_listing.html",
    "<LISTING_URL_PAGE_1>": "{name}_listing.html",
    "<DETAIL_URL>": "{name}_detail.html",
```

Add scraper fixtures:
```python
from scraper.scrapers.{name} import {PascalCase}Scraper

@pytest.fixture
def static_{name}_scraper():
    def _factory(html: str) -> {PascalCase}Scraper:
        return {PascalCase}Scraper(fetch=StaticFetch(html))
    return _factory

@pytest.fixture
def {name}_scraper(mock_fetch: MockFetch) -> {PascalCase}Scraper:
    return {PascalCase}Scraper(
        fetch=mock_fetch,
        base_url="<LISTING_URL>",
    )
```

**9b. Create test file `services/scraper/tests/scrapers/test_{name}.py`:**

```python
import pytest

from scraper.enums import ListingStatus
from scraper.models import DetailListing


def test_scrape_first_page({name}_scraper):
    listings = {name}_scraper._scrape_page(page_number=1)

    assert len(listings) > 0
    assert all(listing.website == "{name}" for listing in listings)
    assert all(listing.detail_url for listing in listings)
    assert all(listing.title for listing in listings)


def test_scrape_list_card_fields({name}_scraper):
    listings = {name}_scraper._scrape_page(page_number=1)

    for listing in listings:
        assert listing.detail_url.startswith("http")
        assert listing.title
        assert listing.price.startswith("€"), f"unexpected price: {listing.price!r}"
        assert listing.street, f"missing street for {listing.detail_url}"
        assert listing.house_number is not None, f"missing house_number for {listing.detail_url}"
        assert listing.city and listing.city != "unknown", f"missing city for {listing.detail_url}"


def test_first_card_specifics({name}_scraper):
    listings = {name}_scraper._scrape_page(page_number=1)
    first = listings[0]

    # Fill in from the actual first card in the fixture HTML:
    assert first.title == "<FIRST_CARD_TITLE>"
    assert first.street == "<FIRST_CARD_STREET>"
    assert first.house_number == <FIRST_CARD_NUMBER>
    assert first.city == "<FIRST_CARD_CITY>"


DETAIL_URL = "<DETAIL_URL>"


def test_scrape_detail_returns_detail_listing({name}_scraper):
    detail = {name}_scraper.scrape_detail(DETAIL_URL)

    assert isinstance(detail, DetailListing)
    assert detail.price  # starts with €
    # Fill in expected values from the fixture HTML:
    assert detail.price == "<EXPECTED_PRICE>"
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 == <EXPECTED_SURFACE>
    assert detail.room_count == <EXPECTED_ROOMS>
    assert detail.bedroom_count == <EXPECTED_BEDROOMS>
    assert detail.bathroom_count == <EXPECTED_BATHROOMS>
    assert detail.construction_period == "<EXPECTED_PERIOD>"
    assert detail.energy_label == "<EXPECTED_LABEL>"
    assert detail.postcode == "<EXPECTED_POSTCODE>"


def test_scrape_detail_returns_none_for_absent_fields(static_{name}_scraper):
    minimal_html = """
    <html><body>
    <MINIMAL_PRICE_HTML>
    </body></html>
    """
    scraper = static_{name}_scraper(minimal_html)
    detail = scraper.scrape_detail("https://example.com/listing")

    assert detail.price == "<MINIMAL_PRICE>"
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 is None
    assert detail.bedroom_count is None
    assert detail.bathroom_count is None
    assert detail.room_count is None
    assert detail.construction_period is None
    assert detail.energy_label is None
    assert detail.postcode is None
```

If `DETECTION_MARKERS` is not empty, add:

```python
def test_is_scraping_detected_true({name}_scraper):
    blocked_html = "<html><body><DETECTION_MARKER_TEXT></body></html>"
    assert {name}_scraper.is_scraping_detected(blocked_html) is True


def test_is_scraping_detected_false({name}_scraper, mock_fetch):
    normal_html = mock_fetch.fetch("<LISTING_URL>")
    assert {name}_scraper.is_scraping_detected(normal_html) is False
```

All `<PLACEHOLDER>` values must be filled in from the actual fixture HTML during generation. Do NOT leave any placeholders — read the saved fixture files and extract the real values.

### Step 10: Run tests and present for review

Run the tests to verify everything works:

```bash
cd services/scraper && uv run pytest tests/scrapers/test_{name}.py -v
```

If tests fail, fix the scraper code based on the error output. Common issues:
- Selector doesn't match the fixture HTML (typo, wrong class name)
- URL construction doesn't match the `URL_TO_FILE` mapping
- Missing import

After tests pass, also run the full test suite to check for regressions:

```bash
cd services/scraper && uv run pytest tests/ -v
```

And pre-commit checks:

```bash
make pre-commit
```

**Present all generated files for user review.** Do NOT commit — wait for the user's sign-off per the repo's review-before-commit convention.

## Error Handling

| Situation | Action |
|---|---|
| Playwright can't load the page | Report error, ask user to verify URL |
| No card pattern detected in snapshot | Fall back to fully guided: ask user to describe the card structure (CSS class, tag name) |
| HTTP comparison `curl` fails | Default to `PlaywrightFetch`, note the failure |
| Detail page link broken | Try the next card's URL, up to 3 attempts |
| Field not found on detail page | Ask user: skip (return `None`) or provide the selector |
| Test failures after generation | Read the error, fix the selector/assertion, re-run |

## Reference: Existing Scraper Architecture

Files the generated code integrates with:

- `services/scraper/src/scraper/scrapers/base.py` — `BaseScraper` base class with `get_soup()` + `detection_markers`
- `services/scraper/src/scraper/protocols.py` — `FetchStrategy`, `ListScraper`, `DetailScraper` protocols
- `services/scraper/src/scraper/models.py` — `Listing` and `DetailListing` Pydantic models
- `services/scraper/src/scraper/enums.py` — `Website`, `ListingStatus` enums
- `services/scraper/src/scraper/runner.py` — `PORTAL_SCRAPER_MAP` + `_make_fetch()`
- `services/scraper/src/scraper/address.py` — `parse_dutch_address()`, `parse_dutch_postcode()`
- `services/scraper/src/scraper/status.py` — `detect_status()`
- `services/scraper/tests/conftest.py` — `StaticFetch`, `MockFetch`, `URL_TO_FILE`, fixtures

Existing scrapers for reference (follow the same patterns):
- `services/scraper/src/scraper/scrapers/funda.py` — Playwright, dt/dd detail parsing, query-param pagination
- `services/scraper/src/scraper/scrapers/pararius.py` — Playwright, JSON-LD postcode, path-segment pagination
- `services/scraper/src/scraper/scrapers/vastgoed_nl.py` — HttpFetch, summary cards + dt/dd detail, query-param pagination
