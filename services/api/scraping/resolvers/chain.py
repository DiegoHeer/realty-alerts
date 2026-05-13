from typing import Protocol, Self, runtime_checkable

from scraping.resolvers.kadaster import (
    KadasterConfig,
    KadasterPostcodeResolver,
    KadasterStreetCityResolver,
    _BAG_BASE_URL,
)
from scraping.resolvers.pdok import PdokFuzzyResolver
from scraping.resolvers.types import AddressQuery, AddressResolver, BagLookupFailure, BagLookupResult, BagLookupSuccess


@runtime_checkable
class _Closeable(Protocol):
    def close(self) -> None: ...


class RetryWithoutSpecifics:
    def __init__(self, inner: AddressResolver) -> None:
        self._inner = inner

    def close(self) -> None:
        if isinstance(self._inner, _Closeable):
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
            if isinstance(resolver, _Closeable):
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
    return ChainedResolver(
        [
            RetryWithoutSpecifics(KadasterPostcodeResolver(config)),
            RetryWithoutSpecifics(KadasterStreetCityResolver(config)),
            PdokFuzzyResolver(),
        ]
    )
