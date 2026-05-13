# BAG Resolver Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `BagClient` with an extensible `ChainedResolver` that tries Kadaster postcode → Kadaster street+city → PDOK fuzzy in sequence, recovering from wrong postcodes and abbreviated street names.

**Architecture:** An `AddressResolver` Protocol defines a single `resolve(query) -> BagLookupResult | None` method. Three concrete resolvers handle one strategy each. `RetryWithoutSpecifics` is a decorator resolver that retries without house letter/suffix when the inner resolver returns no results. `ChainedResolver` iterates resolvers and stops at the first success.

**Tech Stack:** Python 3.14, httpx, respx (tests), loguru, Celery, Django Ninja, pytest

---

## File Map

```
services/api/scraping/resolvers/
  __init__.py          new — re-exports public API
  types.py             new — AddressQuery, AddressResolver protocol, BagLookupSuccess/Failure/Result
  chain.py             new — ChainedResolver, RetryWithoutSpecifics, create_resolver()
  kadaster.py          new — KadasterConfig, KadasterPostcodeResolver, KadasterStreetCityResolver, resolve_addresses()
  pdok.py              new — PdokFuzzyResolver

services/api/scraping/
  bag_client.py        DELETE (replaced by resolvers/)
  tasks.py             UPDATE — import from scraping.resolvers, use AddressQuery
  admin.py             UPDATE — import from scraping.resolvers, use AddressQuery

services/api/tests/
  test_bag_client.py          DELETE (replaced)
  test_resolvers_types.py     new — AddressQuery tests
  test_resolvers_kadaster.py  new — Kadaster resolver unit tests (migrates test_bag_client.py)
  test_resolvers_pdok.py      new — PdokFuzzyResolver unit tests
  test_resolvers_chain.py     new — ChainedResolver + RetryWithoutSpecifics tests
  test_tasks.py               UPDATE — change imports, add wrong-postcode test
```

---

## Task 1: Foundation types

**Files:**
- Create: `services/api/scraping/resolvers/types.py`
- Create: `services/api/tests/test_resolvers_types.py`

- [ ] **Step 1: Write the failing test**

```python
# services/api/tests/test_resolvers_types.py
from scraping.resolvers.types import AddressQuery


def test_without_specifics_strips_letter_and_suffix():
    q = AddressQuery(postcode="1271KE", house_number=9, house_letter="R", house_number_suffix="A59")
    stripped = q.without_specifics()
    assert stripped.postcode == "1271KE"
    assert stripped.house_number == 9
    assert stripped.house_letter is None
    assert stripped.house_number_suffix is None
    assert stripped.street is None
    assert stripped.city is None


def test_without_specifics_preserves_street_and_city():
    q = AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen", house_letter="R")
    stripped = q.without_specifics()
    assert stripped.street == "Klaterweg"
    assert stripped.city == "Huizen"
    assert stripped.house_letter is None


def test_without_specifics_on_already_bare_query_is_idempotent():
    q = AddressQuery(postcode="1271KE", house_number=9)
    assert q.without_specifics() == q
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd services/api && uv run pytest tests/test_resolvers_types.py -v
```

Expected: `ImportError: cannot import name 'AddressQuery' from 'scraping.resolvers.types'`

- [ ] **Step 3: Create the package directory and types module**

```bash
mkdir -p services/api/scraping/resolvers
touch services/api/scraping/resolvers/__init__.py
```

```python
# services/api/scraping/resolvers/types.py
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class BagLookupFailure(StrEnum):
    MISSING_ADDRESS = "missing_address"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class BagLookupSuccess:
    bag_id: str
    street: str
    house_number: int
    house_letter: str | None
    house_number_suffix: str | None
    postcode: str
    city: str


BagLookupResult = BagLookupSuccess | BagLookupFailure


@dataclass(frozen=True)
class AddressQuery:
    postcode: str | None
    house_number: int | None
    house_letter: str | None = None
    house_number_suffix: str | None = None
    street: str | None = None
    city: str | None = None

    def without_specifics(self) -> "AddressQuery":
        return AddressQuery(
            postcode=self.postcode,
            house_number=self.house_number,
            street=self.street,
            city=self.city,
        )


class AddressResolver(Protocol):
    def resolve(self, query: AddressQuery) -> BagLookupResult | None: ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/api && uv run pytest tests/test_resolvers_types.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/resolvers/ services/api/tests/test_resolvers_types.py
git commit -m "feat(api): add resolvers package with AddressQuery and AddressResolver types"
```

---

## Task 2: Kadaster resolvers

**Files:**
- Create: `services/api/scraping/resolvers/kadaster.py`
- Create: `services/api/tests/test_resolvers_kadaster.py`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_resolvers_kadaster.py
import httpx
import pytest
import respx

from scraping.resolvers.kadaster import KadasterConfig, KadasterPostcodeResolver, KadasterStreetCityResolver, resolve_addresses
from scraping.resolvers.types import AddressQuery, BagLookupFailure, BagLookupSuccess

_TEST_BASE_URL = "https://bag.test/v2"


def _config() -> KadasterConfig:
    return KadasterConfig(api_key="test-key", base_url=_TEST_BASE_URL)


def _postcode_resolver() -> KadasterPostcodeResolver:
    return KadasterPostcodeResolver(_config())


def _street_city_resolver() -> KadasterStreetCityResolver:
    return KadasterStreetCityResolver(_config())


def _address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Klaterweg",
        "huisnummer": 9,
        "huisletter": "R",
        "huisnummertoevoeging": "A59",
        "postcode": "1271KE",
        "woonplaatsNaam": "Huizen",
        "nummeraanduidingIdentificatie": "0402200000084467",
    }
    base.update(overrides)
    return base


# --- resolve_addresses ---

def test_resolve_addresses_returns_single_result():
    result = resolve_addresses([_address()], house_letter="R", house_number_suffix="A59")
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"
    assert result.street == "Klaterweg"
    assert result.house_number == 9
    assert result.house_letter == "R"
    assert result.house_number_suffix == "A59"
    assert result.postcode == "1271KE"
    assert result.city == "Huizen"


def test_resolve_addresses_disambiguates_by_letter_and_suffix():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="R", huisnummertoevoeging="A59"),
    ]
    result = resolve_addresses(addresses, house_letter="R", house_number_suffix="A59")
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "002"


def test_resolve_addresses_disambiguates_by_absent_letter():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
    ]
    result = resolve_addresses(addresses, house_letter=None, house_number_suffix=None)
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "001"


def test_resolve_addresses_returns_ambiguous_when_multiple_match():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="A", huisnummertoevoeging=None),
    ]
    assert resolve_addresses(addresses, house_letter="A", house_number_suffix=None) is BagLookupFailure.AMBIGUOUS


def test_resolve_addresses_returns_ambiguous_when_none_match():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
    ]
    assert resolve_addresses(addresses, house_letter="Z", house_number_suffix=None) is BagLookupFailure.AMBIGUOUS


# --- KadasterPostcodeResolver ---

def test_postcode_resolver_returns_none_when_postcode_missing():
    resolver = _postcode_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9))
    assert result is None


def test_postcode_resolver_returns_none_when_house_number_missing():
    resolver = _postcode_resolver()
    result = resolver.resolve(AddressQuery(postcode="1271KE", house_number=None))
    assert result is None


@respx.mock
def test_postcode_resolver_success():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        result = resolver.resolve(
            AddressQuery(postcode="1271 KE", house_number=9, house_letter="R", house_number_suffix="A59")
        )
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"


@respx.mock
def test_postcode_resolver_normalises_postcode():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271 ke", house_number=9))
    assert route.calls.last.request.url.params["postcode"] == "1271KE"


@respx.mock
def test_postcode_resolver_sends_optional_params():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(
            AddressQuery(postcode="1271KE", house_number=9, house_letter="R", house_number_suffix="A59")
        )
    params = route.calls.last.request.url.params
    assert params["huisletter"] == "R"
    assert params["huisnummertoevoeging"] == "A59"


@respx.mock
def test_postcode_resolver_omits_optional_params_when_blank():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address(huisletter=None)]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))
    params = route.calls.last.request.url.params
    assert "huisletter" not in params
    assert "huisnummertoevoeging" not in params


@respx.mock
def test_postcode_resolver_returns_none_on_empty_results():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": []}})
    )
    with _postcode_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode="9999XX", house_number=1))
    assert result is None


@respx.mock
def test_postcode_resolver_returns_none_on_404():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(404))
    with _postcode_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode="9999XX", house_number=1))
    assert result is None


@respx.mock
def test_postcode_resolver_propagates_5xx():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    with _postcode_resolver() as resolver, pytest.raises(httpx.HTTPStatusError):
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))


@respx.mock
def test_postcode_resolver_sends_api_key_header():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))
    assert route.calls.last.request.headers["X-Api-Key"] == "test-key"


# --- KadasterStreetCityResolver ---

def test_street_city_resolver_returns_none_when_street_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street=None, city="Huizen"))
    assert result is None


def test_street_city_resolver_returns_none_when_city_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city=None))
    assert result is None


def test_street_city_resolver_returns_none_when_house_number_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=None, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_street_city_resolver_success():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _street_city_resolver() as resolver:
        result = resolver.resolve(
            AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen")
        )
    assert isinstance(result, BagLookupSuccess)
    params = route.calls.last.request.url.params
    assert params["openbareRuimteNaam"] == "Klaterweg"
    assert params["woonplaatsNaam"] == "Huizen"
    assert "postcode" not in params


@respx.mock
def test_street_city_resolver_returns_none_on_empty_results():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": []}})
    )
    with _street_city_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Nowhere", city="Faketown"))
    assert result is None


@respx.mock
def test_street_city_resolver_returns_none_on_404():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(404))
    with _street_city_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_street_city_resolver_propagates_5xx():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    with _street_city_resolver() as resolver, pytest.raises(httpx.HTTPStatusError):
        resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen"))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/api && uv run pytest tests/test_resolvers_kadaster.py -v
```

Expected: `ImportError: cannot import name 'KadasterConfig'`

- [ ] **Step 3: Create kadaster.py**

```python
# services/api/scraping/resolvers/kadaster.py
from dataclasses import dataclass

import httpx

from scraping.resolvers.types import AddressQuery, BagLookupFailure, BagLookupResult, BagLookupSuccess

_BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"


@dataclass(frozen=True)
class KadasterConfig:
    api_key: str
    base_url: str = _BAG_BASE_URL
    timeout: float = 10.0


def _make_kadaster_client(config: KadasterConfig) -> httpx.Client:
    return httpx.Client(
        base_url=config.base_url,
        headers={
            "X-Api-Key": config.api_key,
            "Accept": "application/hal+json",
            "Accept-Crs": "epsg:28992",
        },
        timeout=config.timeout,
    )


def resolve_addresses(
    addresses: list[dict],
    *,
    house_letter: str | None,
    house_number_suffix: str | None,
) -> BagLookupSuccess | BagLookupFailure:
    if len(addresses) > 1:
        matches = [
            a
            for a in addresses
            if a.get("huisletter") == house_letter and a.get("huisnummertoevoeging") == house_number_suffix
        ]
        if len(matches) != 1:
            return BagLookupFailure.AMBIGUOUS
        addresses = matches
    address = addresses[0]
    return BagLookupSuccess(
        bag_id=address["nummeraanduidingIdentificatie"],
        street=address["openbareRuimteNaam"],
        house_number=int(address["huisnummer"]),
        house_letter=address.get("huisletter"),
        house_number_suffix=address.get("huisnummertoevoeging"),
        postcode=address["postcode"],
        city=address["woonplaatsNaam"],
    )


class KadasterPostcodeResolver:
    def __init__(self, config: KadasterConfig) -> None:
        self._client = _make_kadaster_client(config)

    def __enter__(self) -> "KadasterPostcodeResolver":
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        if not query.postcode or query.house_number is None:
            return None

        params: dict[str, str | int] = {
            "postcode": query.postcode.replace(" ", "").upper(),
            "huisnummer": query.house_number,
        }
        if query.house_letter:
            params["huisletter"] = query.house_letter
        if query.house_number_suffix:
            params["huisnummertoevoeging"] = query.house_number_suffix

        response = self._client.get("/adressen", params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return None
        return resolve_addresses(addresses, house_letter=query.house_letter, house_number_suffix=query.house_number_suffix)


class KadasterStreetCityResolver:
    def __init__(self, config: KadasterConfig) -> None:
        self._client = _make_kadaster_client(config)

    def __enter__(self) -> "KadasterStreetCityResolver":
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        if not query.street or not query.city or query.house_number is None:
            return None

        params: dict[str, str | int] = {
            "openbareRuimteNaam": query.street,
            "woonplaatsNaam": query.city,
            "huisnummer": query.house_number,
        }
        if query.house_letter:
            params["huisletter"] = query.house_letter
        if query.house_number_suffix:
            params["huisnummertoevoeging"] = query.house_number_suffix

        response = self._client.get("/adressen", params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return None
        return resolve_addresses(addresses, house_letter=query.house_letter, house_number_suffix=query.house_number_suffix)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/api && uv run pytest tests/test_resolvers_kadaster.py -v
```

Expected: all tests passed

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/resolvers/kadaster.py services/api/tests/test_resolvers_kadaster.py
git commit -m "feat(api): add KadasterPostcodeResolver and KadasterStreetCityResolver"
```

---

## Task 3: PDOK fuzzy resolver

**Files:**
- Create: `services/api/scraping/resolvers/pdok.py`
- Create: `services/api/tests/test_resolvers_pdok.py`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_resolvers_pdok.py
import httpx
import respx

from scraping.resolvers.pdok import PdokFuzzyResolver
from scraping.resolvers.types import AddressQuery, BagLookupSuccess

_TEST_PDOK_URL = "https://pdok.test/v3"


def _resolver() -> PdokFuzzyResolver:
    return PdokFuzzyResolver(base_url=_TEST_PDOK_URL)


def _suggest_response(doc_id: str = "adr-abc123", score: float = 12.5) -> dict:
    return {"response": {"docs": [{"type": "adres", "id": doc_id, "score": score}]}}


def _lookup_response(**overrides) -> dict:
    doc = {
        "nummeraanduiding_id": "0503200000016590",
        "straatnaam": "Cornelis de Wittstraat",
        "huisnummer": 46,
        "huisletter": None,
        "huisnummertoevoeging": None,
        "postcode": "2613GH",
        "woonplaatsnaam": "Delft",
    }
    doc.update(overrides)
    return {"response": {"docs": [doc]}}


@respx.mock
def test_pdok_resolver_succeeds_with_abbreviated_street():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json=_suggest_response())
    )
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(
        return_value=httpx.Response(200, json=_lookup_response())
    )
    with _resolver() as resolver:
        result = resolver.resolve(
            AddressQuery(postcode=None, house_number=46, street="Corn. de Wittstraat", city="Delft")
        )
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0503200000016590"
    assert result.street == "Cornelis de Wittstraat"
    assert result.house_number == 46
    assert result.postcode == "2613GH"
    assert result.city == "Delft"


@respx.mock
def test_pdok_resolver_query_excludes_postcode():
    route = respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json=_suggest_response())
    )
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(
        return_value=httpx.Response(200, json=_lookup_response())
    )
    with _resolver() as resolver:
        resolver.resolve(
            AddressQuery(postcode="2613GG", house_number=46, street="Cornelis de Wittstraat", city="Delft")
        )
    q = route.calls.last.request.url.params["q"]
    assert "2613GG" not in q
    assert "Cornelis de Wittstraat" in q
    assert "46" in q
    assert "Delft" in q


@respx.mock
def test_pdok_resolver_returns_none_on_empty_suggest():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json={"response": {"docs": []}})
    )
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Corn.", city="Delft"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_when_score_below_threshold():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json=_suggest_response(score=3.0))
    )
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=1, street="Vague", city="City"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_empty_lookup():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json=_suggest_response())
    )
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(
        return_value=httpx.Response(200, json={"response": {"docs": []}})
    )
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Corn.", city="Delft"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_suggest_500():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(500))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_lookup_500():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(
        return_value=httpx.Response(200, json=_suggest_response())
    )
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(return_value=httpx.Response(500))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Klaterweg", city="Huizen"))
    assert result is None


def test_pdok_resolver_returns_none_when_street_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street=None, city="Huizen"))
    assert result is None


def test_pdok_resolver_returns_none_when_city_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city=None))
    assert result is None


def test_pdok_resolver_returns_none_when_house_number_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=None, street="Klaterweg", city="Huizen"))
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/api && uv run pytest tests/test_resolvers_pdok.py -v
```

Expected: `ImportError: cannot import name 'PdokFuzzyResolver'`

- [ ] **Step 3: Create pdok.py**

```python
# services/api/scraping/resolvers/pdok.py
import httpx
from loguru import logger

from scraping.resolvers.types import AddressQuery, BagLookupResult, BagLookupSuccess

_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_MIN_SCORE = 10.0
_LOOKUP_FIELDS = "nummeraanduiding_id,straatnaam,huisnummer,huisletter,huisnummertoevoeging,postcode,woonplaatsnaam"


class PdokFuzzyResolver:
    def __init__(self, base_url: str = _PDOK_BASE_URL, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def __enter__(self) -> "PdokFuzzyResolver":
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        if not query.street or not query.city or query.house_number is None:
            return None
        try:
            return self._suggest_then_lookup(query)
        except Exception as exc:
            logger.warning(
                "PDOK lookup failed for {} {} {}: {}",
                query.street,
                query.house_number,
                query.city,
                exc,
            )
            return None

    def _suggest_then_lookup(self, query: AddressQuery) -> BagLookupSuccess | None:
        q = f"{query.street} {query.house_number} {query.city}"
        suggest = self._client.get("/suggest", params={"q": q, "fq": "type:adres", "rows": 1})
        suggest.raise_for_status()

        docs = suggest.json().get("response", {}).get("docs", [])
        if not docs or docs[0].get("score", 0.0) < _MIN_SCORE:
            return None

        lookup = self._client.get(
            "/lookup", params={"id": docs[0]["id"], "fl": _LOOKUP_FIELDS}
        )
        lookup.raise_for_status()

        results = lookup.json().get("response", {}).get("docs", [])
        if not results:
            return None

        doc = results[0]
        return BagLookupSuccess(
            bag_id=doc["nummeraanduiding_id"],
            street=doc["straatnaam"],
            house_number=int(doc["huisnummer"]),
            house_letter=doc.get("huisletter"),
            house_number_suffix=doc.get("huisnummertoevoeging"),
            postcode=doc["postcode"],
            city=doc["woonplaatsnaam"],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/api && uv run pytest tests/test_resolvers_pdok.py -v
```

Expected: all tests passed

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/resolvers/pdok.py services/api/tests/test_resolvers_pdok.py
git commit -m "feat(api): add PdokFuzzyResolver as last-resort BAG lookup"
```

---

## Task 4: Chain and decorator

**Files:**
- Create: `services/api/scraping/resolvers/chain.py`
- Create: `services/api/tests/test_resolvers_chain.py`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_resolvers_chain.py
import pytest

from scraping.resolvers.chain import ChainedResolver, RetryWithoutSpecifics
from scraping.resolvers.types import AddressQuery, BagLookupFailure, BagLookupResult, BagLookupSuccess

_SUCCESS = BagLookupSuccess(
    bag_id="0402200000084467",
    street="Klaterweg",
    house_number=9,
    house_letter="R",
    house_number_suffix="A59",
    postcode="1271KE",
    city="Huizen",
)

_QUERY = AddressQuery(postcode="1271KE", house_number=9)
_QUERY_WITH_SPECIFICS = AddressQuery(postcode="1271KE", house_number=9, house_letter="R", house_number_suffix="A59")
_QUERY_STREET_CITY = AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen")


class _MockResolver:
    def __init__(self, returns: BagLookupResult | None) -> None:
        self.calls: list[AddressQuery] = []
        self.closed = False
        self._returns = returns

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        self.calls.append(query)
        return self._returns

    def close(self) -> None:
        self.closed = True


# --- ChainedResolver pre-checks ---

def test_chain_returns_missing_address_when_house_number_none():
    chain = ChainedResolver([])
    result = chain.resolve(AddressQuery(postcode="1271KE", house_number=None))
    assert result is BagLookupFailure.MISSING_ADDRESS


def test_chain_returns_missing_address_when_no_postcode_and_no_street_city():
    chain = ChainedResolver([])
    result = chain.resolve(AddressQuery(postcode=None, house_number=9, street=None, city=None))
    assert result is BagLookupFailure.MISSING_ADDRESS


def test_chain_returns_missing_address_when_no_postcode_and_street_but_no_city():
    chain = ChainedResolver([])
    result = chain.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city=None))
    assert result is BagLookupFailure.MISSING_ADDRESS


# --- ChainedResolver iteration ---

def test_chain_stops_at_first_success():
    r1 = _MockResolver(returns=_SUCCESS)
    r2 = _MockResolver(returns=_SUCCESS)
    chain = ChainedResolver([r1, r2])
    result = chain.resolve(_QUERY)
    assert isinstance(result, BagLookupSuccess)
    assert len(r1.calls) == 1
    assert len(r2.calls) == 0


def test_chain_skips_none_and_continues():
    r1 = _MockResolver(returns=None)
    r2 = _MockResolver(returns=_SUCCESS)
    result = ChainedResolver([r1, r2]).resolve(_QUERY)
    assert isinstance(result, BagLookupSuccess)
    assert len(r1.calls) == 1
    assert len(r2.calls) == 1


def test_chain_skips_ambiguous_and_continues():
    r1 = _MockResolver(returns=BagLookupFailure.AMBIGUOUS)
    r2 = _MockResolver(returns=_SUCCESS)
    result = ChainedResolver([r1, r2]).resolve(_QUERY)
    assert isinstance(result, BagLookupSuccess)
    assert len(r2.calls) == 1


def test_chain_returns_no_match_when_all_return_none():
    result = ChainedResolver([_MockResolver(None), _MockResolver(None)]).resolve(_QUERY)
    assert result is BagLookupFailure.NO_MATCH


def test_chain_returns_ambiguous_when_any_resolver_returned_ambiguous():
    result = ChainedResolver([
        _MockResolver(BagLookupFailure.AMBIGUOUS),
        _MockResolver(None),
    ]).resolve(_QUERY)
    assert result is BagLookupFailure.AMBIGUOUS


def test_chain_returns_no_match_when_all_return_none_and_none_saw_ambiguous():
    result = ChainedResolver([_MockResolver(None)]).resolve(_QUERY)
    assert result is BagLookupFailure.NO_MATCH


# --- ChainedResolver context manager ---

def test_chain_closes_all_resolvers_on_exit():
    r1 = _MockResolver(None)
    r2 = _MockResolver(None)
    with ChainedResolver([r1, r2]):
        pass
    assert r1.closed
    assert r2.closed


def test_chain_closes_resolvers_even_on_exception():
    r1 = _MockResolver(None)
    with pytest.raises(RuntimeError):
        with ChainedResolver([r1]) as chain:
            raise RuntimeError("test")
    assert r1.closed


# --- RetryWithoutSpecifics ---

def test_retry_passes_through_success_without_retry():
    inner = _MockResolver(returns=_SUCCESS)
    resolver = RetryWithoutSpecifics(inner)
    result = resolver.resolve(_QUERY_WITH_SPECIFICS)
    assert isinstance(result, BagLookupSuccess)
    assert len(inner.calls) == 1


def test_retry_does_not_retry_when_no_letter_or_suffix():
    inner = _MockResolver(returns=None)
    resolver = RetryWithoutSpecifics(inner)
    result = resolver.resolve(_QUERY)
    assert result is None
    assert len(inner.calls) == 1


def test_retry_retries_without_letter_when_initial_returns_none():
    inner = _MockResolver(returns=None)
    # Override to succeed on second call (bare query)
    call_count = 0
    original_returns = [None, _SUCCESS]

    class SequentialMock:
        calls: list[AddressQuery] = []
        closed = False

        def resolve(self, query: AddressQuery) -> BagLookupResult | None:
            self.calls.append(query)
            return original_returns[len(self.calls) - 1]

        def close(self) -> None:
            self.closed = True

    seq = SequentialMock()
    resolver = RetryWithoutSpecifics(seq)
    result = resolver.resolve(_QUERY_WITH_SPECIFICS)
    assert isinstance(result, BagLookupSuccess)
    assert len(seq.calls) == 2
    assert seq.calls[0].house_letter == "R"
    assert seq.calls[1].house_letter is None
    assert seq.calls[1].house_number_suffix is None


def test_retry_returns_none_when_retry_is_ambiguous():
    results = [None, BagLookupFailure.AMBIGUOUS]

    class SequentialMock:
        calls: list[AddressQuery] = []
        closed = False

        def resolve(self, query: AddressQuery) -> BagLookupResult | None:
            self.calls.append(query)
            return results[len(self.calls) - 1]

        def close(self) -> None:
            pass

    result = RetryWithoutSpecifics(SequentialMock()).resolve(_QUERY_WITH_SPECIFICS)
    assert result is None


def test_retry_delegates_close_to_inner():
    inner = _MockResolver(None)
    resolver = RetryWithoutSpecifics(inner)
    resolver.close()
    assert inner.closed
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/api && uv run pytest tests/test_resolvers_chain.py -v
```

Expected: `ImportError: cannot import name 'ChainedResolver'`

- [ ] **Step 3: Create chain.py**

```python
# services/api/scraping/resolvers/chain.py
from typing import Self

from scraping.resolvers.kadaster import KadasterConfig, KadasterPostcodeResolver, KadasterStreetCityResolver, _BAG_BASE_URL
from scraping.resolvers.pdok import PdokFuzzyResolver
from scraping.resolvers.types import AddressQuery, AddressResolver, BagLookupFailure, BagLookupResult, BagLookupSuccess


class RetryWithoutSpecifics:
    def __init__(self, inner: AddressResolver) -> None:
        self._inner = inner

    def close(self) -> None:
        if hasattr(self._inner, "close"):
            self._inner.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        result = self._inner.resolve(query)
        if result is not None:
            return result
        if not (query.house_letter or query.house_number_suffix):
            return None
        retried = self._inner.resolve(query.without_specifics())
        if retried is BagLookupFailure.AMBIGUOUS:
            return None
        return retried


class ChainedResolver:
    def __init__(self, resolvers: list[AddressResolver]) -> None:
        self._resolvers = resolvers

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        for resolver in self._resolvers:
            if hasattr(resolver, "close"):
                resolver.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult:
        if query.house_number is None:
            return BagLookupFailure.MISSING_ADDRESS
        if not query.postcode and not (query.street and query.city):
            return BagLookupFailure.MISSING_ADDRESS

        saw_ambiguous = False
        for resolver in self._resolvers:
            result = resolver.resolve(query)
            if result is None:
                continue
            if isinstance(result, BagLookupSuccess):
                return result
            if result is BagLookupFailure.AMBIGUOUS:
                saw_ambiguous = True
        return BagLookupFailure.AMBIGUOUS if saw_ambiguous else BagLookupFailure.NO_MATCH


def create_resolver(*, api_key: str, base_url: str = _BAG_BASE_URL, timeout: float = 10.0) -> ChainedResolver:
    config = KadasterConfig(api_key=api_key, base_url=base_url, timeout=timeout)
    return ChainedResolver([
        RetryWithoutSpecifics(KadasterPostcodeResolver(config)),
        RetryWithoutSpecifics(KadasterStreetCityResolver(config)),
        PdokFuzzyResolver(),
    ])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/api && uv run pytest tests/test_resolvers_chain.py -v
```

Expected: all tests passed

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/resolvers/chain.py services/api/tests/test_resolvers_chain.py
git commit -m "feat(api): add ChainedResolver, RetryWithoutSpecifics, and create_resolver factory"
```

---

## Task 5: Package re-exports

**Files:**
- Modify: `services/api/scraping/resolvers/__init__.py`

- [ ] **Step 1: Write the re-exports**

```python
# services/api/scraping/resolvers/__init__.py
from scraping.resolvers.chain import ChainedResolver, RetryWithoutSpecifics, create_resolver
from scraping.resolvers.types import (
    AddressQuery,
    AddressResolver,
    BagLookupFailure,
    BagLookupResult,
    BagLookupSuccess,
)

__all__ = [
    "AddressQuery",
    "AddressResolver",
    "BagLookupFailure",
    "BagLookupResult",
    "BagLookupSuccess",
    "ChainedResolver",
    "RetryWithoutSpecifics",
    "create_resolver",
]
```

- [ ] **Step 2: Verify imports work**

```bash
cd services/api && uv run python -c "from scraping.resolvers import create_resolver, AddressQuery, BagLookupFailure, BagLookupSuccess; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run the full resolver test suite**

```bash
cd services/api && uv run pytest tests/test_resolvers_types.py tests/test_resolvers_kadaster.py tests/test_resolvers_pdok.py tests/test_resolvers_chain.py -v
```

Expected: all tests passed

- [ ] **Step 4: Commit**

```bash
git add services/api/scraping/resolvers/__init__.py
git commit -m "feat(api): expose resolvers public API via package __init__"
```

---

## Task 6: Update callers

**Files:**
- Modify: `services/api/scraping/tasks.py`
- Modify: `services/api/scraping/admin.py`
- Modify: `services/api/tests/test_tasks.py`

- [ ] **Step 1: Update tasks.py**

Replace the `from scraping.bag_client import ...` import block and the `resolve_bag` body:

```python
# services/api/scraping/tasks.py
# Change this import:
#   from scraping.bag_client import BagClient, BagLookupFailure, BagLookupSuccess
# To:
from scraping.resolvers import BagLookupFailure, BagLookupSuccess, create_resolver
from scraping.resolvers.types import AddressQuery

# _FAILURE_TO_BAG_STATUS stays identical — BagLookupFailure values are unchanged.

# Replace resolve_bag body:
@shared_task(
    name="scraping.resolve_bag",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    rate_limit="5/s",
)
def resolve_bag(listing_id: int) -> None:
    listing = Listing.objects.filter(pk=listing_id).first()
    if listing is None or listing.bag_status != BagStatus.PENDING:
        return

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        result = resolver.resolve(
            AddressQuery(
                postcode=listing.postcode,
                house_number=listing.house_number,
                house_letter=listing.house_letter,
                house_number_suffix=listing.house_number_suffix,
                street=listing.street,
                city=listing.city,
            )
        )

    if isinstance(result, BagLookupSuccess):
        residence, _ = Residence.objects.get_or_create(
            bag_id=result.bag_id,
            defaults=_residence_defaults_from_lookup(result, listing),
        )
        listing.residence = residence
        listing.bag_status = BagStatus.RESOLVED
        listing.bag_resolved_at = timezone.now()
        listing.save(update_fields=["residence", "bag_status", "bag_resolved_at"])
        reconcile_residence(residence)
        return

    listing.bag_status = _FAILURE_TO_BAG_STATUS[result]
    listing.bag_failure_reason = f"BAG lookup: {result.value}"
    listing.save(update_fields=["bag_status", "bag_failure_reason"])
```

- [ ] **Step 2: Update admin.py**

```python
# services/api/scraping/admin.py
# Change import:
#   from scraping.bag_client import BagClient, BagLookupFailure
# To:
from scraping.resolvers import BagLookupFailure, BagLookupSuccess, ChainedResolver, create_resolver
from scraping.resolvers.types import AddressQuery

# _FAILURE_TO_BAG_STATUS and _FAILURE_MESSAGES stay identical.

# Update _promote_listing signature and body:
def _promote_listing(listing: Listing, resolver: ChainedResolver) -> str | None:
    if listing.bag_status not in _FAILED_BAG_STATUSES:
        return f"skipped — bag_status is {listing.bag_status}, not a failed state"

    try:
        result = resolver.resolve(
            AddressQuery(
                postcode=listing.postcode,
                house_number=listing.house_number,
                house_letter=listing.house_letter,
                house_number_suffix=listing.house_number_suffix,
                street=listing.street,
                city=listing.city,
            )
        )
    except httpx.HTTPError as exc:
        return f"BAG API error — {exc}"

    if isinstance(result, BagLookupFailure):
        listing.bag_status = _FAILURE_TO_BAG_STATUS[result]
        listing.bag_failure_reason = f"BAG lookup: {result.value}"
        listing.save(update_fields=["bag_status", "bag_failure_reason"])
        return _FAILURE_MESSAGES[result]

    residence, _ = Residence.objects.get_or_create(
        bag_id=result.bag_id,
        defaults={
            "city": result.city,
            "street": result.street,
            "house_number": result.house_number,
            "house_letter": result.house_letter,
            "house_number_suffix": result.house_number_suffix,
            "postcode": result.postcode,
            "current_status": listing.status,
            "status_changed_at": timezone.now(),
            "last_scraped_at": listing.scraped_at,
        },
    )
    listing.residence = residence
    listing.bag_status = BagStatus.RESOLVED
    listing.bag_resolved_at = timezone.now()
    listing.bag_failure_reason = ""
    listing.save(update_fields=["residence", "bag_status", "bag_resolved_at", "bag_failure_reason"])
    reconcile_residence(residence)
    return None


@admin.action(description="Promote selected listings")
def promote_listings(modeladmin, request, queryset):
    succeeded = 0
    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        for listing in queryset:
            error = _promote_listing(listing, resolver)
            if error is None:
                succeeded += 1
            else:
                modeladmin.message_user(
                    request,
                    f"Listing {listing.pk} ({listing.url}): {error}",
                    messages.WARNING,
                )
    if succeeded:
        modeladmin.message_user(
            request,
            f"Successfully promoted {succeeded} listing(s).",
            messages.SUCCESS,
        )
```

- [ ] **Step 3: Update test_tasks.py**

Change the import and add one new test for the wrong-postcode fallback:

```python
# In test_tasks.py, change:
#   from scraping.bag_client import _BAG_BASE_URL
# To:
from scraping.resolvers.kadaster import _BAG_BASE_URL

# Add this new test after the existing tests:

@pytest.mark.django_db
@respx.mock
def test_resolve_bag_falls_back_to_street_city_when_postcode_wrong():
    """A wrong postcode causes postcode path to return empty, chain advances to street+city."""
    from scraping.tasks import resolve_bag

    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        params = request.url.params
        if "postcode" in params:
            return httpx.Response(200, json={"_embedded": {"adressen": []}})
        return httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(side_effect=handler)
    listing = _pending_listing(postcode="1271XX", street="Klaterweg", city="Huizen")

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence is not None
    assert listing.residence.bag_id == "0402200000084467"
    assert call_count == 2  # postcode attempt + street+city fallback
```

- [ ] **Step 4: Run tests to verify callers still work**

```bash
cd services/api && uv run pytest tests/test_tasks.py tests/test_listing_promotion.py -v
```

Expected: all tests passed including the new wrong-postcode test

- [ ] **Step 5: Commit**

```bash
git add services/api/scraping/tasks.py services/api/scraping/admin.py services/api/tests/test_tasks.py
git commit -m "feat(api): wire resolve_bag and promote_listings to use ChainedResolver"
```

---

## Task 7: Cleanup — delete bag_client.py and old tests

**Files:**
- Delete: `services/api/scraping/bag_client.py`
- Delete: `services/api/tests/test_bag_client.py`

- [ ] **Step 1: Delete the old files**

```bash
rm services/api/scraping/bag_client.py
rm services/api/tests/test_bag_client.py
```

- [ ] **Step 2: Run the full test suite to confirm nothing references the deleted files**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all tests passed. If `ImportError: cannot import name ... from 'scraping.bag_client'` appears, search for remaining references:

```bash
grep -r "bag_client" services/api/ --include="*.py"
```

- [ ] **Step 3: Run pre-commit checks**

```bash
make pre-commit
```

Expected: all checks pass (ruff, ty, whitespace, YAML/TOML)

- [ ] **Step 4: Commit**

```bash
git add -u  # stage deletions
git commit -m "refactor(api): remove BagClient in favour of resolver chain"
```

---

## Final verification

- [ ] Run `make test` from the repo root — scraper + api + mobile + web tests all pass
- [ ] Run `make pre-commit` — all hooks pass
- [ ] Manual smoke test (optional, needs BAG API key in env):

```bash
cd services/api && uv run python -c "
from realty_api.settings import base
from scraping.resolvers import create_resolver, AddressQuery

with create_resolver(api_key='YOUR_KEY') as r:
    # Wrong postcode — should resolve via street+city (step 2)
    result = r.resolve(AddressQuery(postcode='2613GG', house_number=46, street='Cornelis de Wittstraat', city='Delft'))
    print('wrong postcode test:', result)

    # Abbreviated street, no postcode — should resolve via PDOK (step 3)
    result = r.resolve(AddressQuery(postcode=None, house_number=46, street='Corn. de Wittstraat', city='Delft'))
    print('abbreviated street test:', result)
"
```
