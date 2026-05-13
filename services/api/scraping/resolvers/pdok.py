import httpx
from loguru import logger

from scraping.resolvers.types import AddressQuery, BagLookupResult, BagLookupSuccess

_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_MIN_SCORE = 10.0
_LOOKUP_FIELDS = "nummeraanduiding_id,straatnaam,huisnummer,huisletter,huisnummertoevoeging,postcode,woonplaatsnaam"


class PdokFuzzyResolver:
    def __init__(self, base_url: str = _PDOK_BASE_URL, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def __enter__(self) -> PdokFuzzyResolver:
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

        lookup = self._client.get("/lookup", params={"id": docs[0]["id"], "fl": _LOOKUP_FIELDS})
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
