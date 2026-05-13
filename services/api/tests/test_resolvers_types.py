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
