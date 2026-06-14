import pytest

from scraping.services.cbs import _clean_stats, _extract_geometry


class TestCleanStats:
    def test_strips_sentinel_values(self):
        raw = {"woningvoorraad": 1200, "gemiddeldeWoningwaarde": -99997}
        result = _clean_stats(raw)
        assert result == {"woningvoorraad": 1200, "gemiddeldeWoningwaarde": None}

    def test_strips_all_sentinel_variants(self):
        raw = {"a": -99997, "b": -99998, "c": -99999998, "d": -99999997}
        result = _clean_stats(raw)
        assert all(v is None for v in result.values())

    def test_strips_large_negative_sentinels(self):
        raw = {"a": -99995}
        result = _clean_stats(raw)
        assert result == {"a": None}

    def test_preserves_valid_values(self):
        raw = {"a": 42, "b": 3.14, "c": "text", "d": None}
        result = _clean_stats(raw)
        assert result == {"a": 42, "b": 3.14, "c": "text", "d": None}

    def test_preserves_valid_negative_values(self):
        raw = {"a": -5, "b": -100}
        result = _clean_stats(raw)
        assert result == {"a": -5, "b": -100}


class TestExtractGeometry:
    def test_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[4.123456789, 52.123456789], [4.2, 52.2], [4.3, 52.1], [4.123456789, 52.123456789]]],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert result[0][0][0] == [4.12346, 52.12346]

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[4.1, 52.1], [4.2, 52.2], [4.3, 52.1], [4.1, 52.1]]],
                [[[4.4, 52.4], [4.5, 52.5], [4.6, 52.4], [4.4, 52.4]]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 2

    def test_returns_empty_for_unsupported_type(self):
        geom = {"type": "Point", "coordinates": [4.1, 52.1]}
        result = _extract_geometry(geom)
        assert result == []

    def test_preserves_holes(self):
        geom = {
            "type": "Polygon",
            "coordinates": [
                [[4.1, 52.1], [4.2, 52.2], [4.3, 52.1], [4.1, 52.1]],
                [[4.15, 52.12], [4.18, 52.15], [4.22, 52.12], [4.15, 52.12]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert len(result[0]) == 2
