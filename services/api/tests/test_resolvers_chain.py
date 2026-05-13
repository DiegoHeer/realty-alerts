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
    result = ChainedResolver(
        [
            _MockResolver(BagLookupFailure.AMBIGUOUS),
            _MockResolver(None),
        ]
    ).resolve(_QUERY)
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
        with ChainedResolver([r1]):
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
