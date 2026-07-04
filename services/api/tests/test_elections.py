import csv
import io
import zipfile
from dataclasses import dataclass, field
from typing import cast
from unittest.mock import patch

import pytest

from scraping.models import City, District, Neighborhood
from scraping.services import elections
from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory

# A unit square and its neighbour, in [polygon][ring][point] nesting as
# stored on Neighborhood.geometry.
SQUARE_A = [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]]
SQUARE_B = [[[[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]]]
SQUARE_WITH_HOLE = [
    [
        [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0], [0.0, 0.0]],
        [[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0], [1.0, 1.0]],
    ]
]


class TestPointInGeometry:
    def test_inside(self):
        assert elections.point_in_geometry(0.5, 0.5, SQUARE_A)

    def test_outside(self):
        assert not elections.point_in_geometry(1.5, 0.5, SQUARE_A)

    def test_inside_hole_is_outside(self):
        assert elections.point_in_geometry(0.5, 0.5, SQUARE_WITH_HOLE)
        assert not elections.point_in_geometry(2.0, 2.0, SQUARE_WITH_HOLE)

    def test_distance_prefers_closer_geometry(self):
        # A point just right of square A is closer to B's edge at x=1..2.
        near_b = elections.distance_sq_to_geometry(2.1, 0.5, SQUARE_B)
        near_a = elections.distance_sq_to_geometry(2.1, 0.5, SQUARE_A)
        assert near_b < near_a


@dataclass
class _District:
    code: str


@dataclass
class _Neighborhood:
    code: str
    district: _District | None = None
    geometry: list | None = field(default=None)


def _station(number: int, votes: dict[str, int], lon=None, lat=None) -> elections.Station:
    return elections.Station(gemeente_code="0518", number=number, votes=votes, lon=lon, lat=lat)


class TestAggregateCity:
    def test_assigns_stations_and_falls_back_to_wijk(self):
        wijk = _District("WK051801")
        buurten = [
            _Neighborhood("BU05180001", wijk, SQUARE_A),
            _Neighborhood("BU05180002", wijk, SQUARE_B),
            _Neighborhood("BU05180003", _District("WK051802"), None),  # no geometry, other wijk
        ]
        stations = {
            1: _station(1, {"D66": 100, "VVD": 50}, lon=0.5, lat=0.5),  # in A
            2: _station(2, {"D66": 10, "CDA": 30}, lon=1.5, lat=0.5),  # in B
            3: _station(3, {"BBB": 7}),  # unlocated (postal bureau)
        }

        result = elections.aggregate_city(stations, buurten)

        assert result.city == {
            "totalVotes": 197,
            "stationCount": 3,
            "source": "gemeente",
            "parties": {"D66": 110, "VVD": 50, "CDA": 30, "BBB": 7},
        }
        assert result.neighborhoods["BU05180001"] == {
            "totalVotes": 150,
            "stationCount": 1,
            "source": "buurt",
            "parties": {"D66": 100, "VVD": 50},
        }
        # Both located stations share wijk WK051801.
        assert result.districts["WK051801"]["totalVotes"] == 190
        assert result.districts["WK051801"]["stationCount"] == 2
        # Buurt without geometry cannot host a station and its wijk has no
        # stations either -> stays empty.
        assert "BU05180003" not in result.neighborhoods
        assert result.empty_neighborhoods == 1
        assert result.located_stations == 2
        assert result.total_stations == 3

    def test_station_outside_all_polygons_goes_to_nearest_buurt(self):
        buurten = [
            _Neighborhood("BU05180001", _District("WK051801"), SQUARE_A),
            _Neighborhood("BU05180002", _District("WK051801"), SQUARE_B),
        ]
        stations = {1: _station(1, {"D66": 5}, lon=2.05, lat=0.5)}  # just outside B

        result = elections.aggregate_city(stations, buurten)

        assert result.neighborhoods["BU05180002"]["parties"] == {"D66": 5}
        assert result.neighborhoods["BU05180001"]["source"] == "wijk"

    def test_wijk_fallback_is_flagged(self):
        wijk = _District("WK051801")
        buurten = [
            _Neighborhood("BU05180001", wijk, SQUARE_A),
            _Neighborhood("BU05180002", wijk, SQUARE_B),
        ]
        stations = {1: _station(1, {"VVD": 40}, lon=0.5, lat=0.5)}

        result = elections.aggregate_city(stations, buurten)

        assert result.neighborhoods["BU05180001"]["source"] == "buurt"
        assert result.neighborhoods["BU05180002"] == {
            "totalVotes": 40,
            "stationCount": 1,
            "source": "wijk",
            "parties": {"VVD": 40},
        }
        assert result.fallback_neighborhoods == 1


class TestParsers:
    def test_parse_votes_and_locations_join(self, tmp_path):
        votes_zip = tmp_path / "votes.zip"
        rows = [
            [
                "GemeenteCode",
                "GemeenteNaam",
                "Postcode",
                "StembureauNaam",
                "StembureauCode",
                "PartijNaam",
                "AantalStemmen",
            ],  # noqa: E501
            ["518", "'s-Gravenhage", "2566AW", "Stembureau X", "SB101", "D66", "12"],
            ["518", "'s-Gravenhage", "2566AW", "Stembureau X", "SB101", "VVD", "8"],
            ["14", "Groningen", "9712HN", "Stadhuis", "SB100", "D66", "3"],
        ]
        buf = io.StringIO()
        csv.writer(buf, delimiter=";").writerows(rows)
        with zipfile.ZipFile(votes_zip, "w") as zf:
            zf.writestr(elections.VOTES_CSV_NAME, buf.getvalue())

        locations_csv = tmp_path / "locations.csv"
        with locations_csv.open("w") as f:
            writer = csv.writer(f)
            writer.writerow(["CBS gemeentecode", "Nummer stembureau", "Latitude", "Longitude"])
            writer.writerow(["GM0518", "101", "52.06", "4.28"])
            writer.writerow(["GM0014", "", "", ""])  # unparsable -> skipped

        stations = elections.parse_votes(votes_zip)
        locations = elections.parse_locations(locations_csv)
        elections.attach_locations(stations, locations)

        assert stations["0518"][101].votes == {"D66": 12, "VVD": 8}
        assert stations["0518"][101].total == 20
        assert (stations["0518"][101].lon, stations["0518"][101].lat) == (4.28, 52.06)
        assert stations["0014"][100].lon is None


def _den_haag_stations():
    """One located station in SQUARE_A with 20 votes, as `load_stations` returns it."""
    return {
        "0518": {1: elections.Station(gemeente_code="0518", number=1, votes={"D66": 12, "VVD": 8}, lon=0.5, lat=0.5)}
    }


@pytest.mark.django_db
class TestLoadElectionStatsTask:
    def test_loads_stats_for_city_districts_and_neighborhoods(self):
        from scraping.tasks import load_election_stats

        city = cast(City, CityFactory(code="0518"))
        district = cast(District, DistrictFactory(code="WK051801", city=city))
        buurt = cast(
            Neighborhood, NeighborhoodFactory(code="BU05180001", city=city, district=district, geometry=SQUARE_A)
        )
        fallback_buurt = cast(
            Neighborhood, NeighborhoodFactory(code="BU05180002", city=city, district=district, geometry=SQUARE_B)
        )

        with patch("scraping.tasks.elections.load_stations", return_value=_den_haag_stations()):
            load_election_stats(city.pk)

        city.refresh_from_db()
        district.refresh_from_db()
        buurt.refresh_from_db()
        fallback_buurt.refresh_from_db()
        assert (city.election_stats or {})["tk2025"]["totalVotes"] == 20
        assert city.election_stats_fetched_at is not None
        assert (district.election_stats or {})["tk2025"]["source"] == "wijk"
        assert (buurt.election_stats or {})["tk2025"] == {
            "totalVotes": 20,
            "stationCount": 1,
            "source": "buurt",
            "parties": {"D66": 12, "VVD": 8},
        }
        assert (fallback_buurt.election_stats or {})["tk2025"]["source"] == "wijk"

    def test_no_op_when_city_has_no_stations(self):
        from scraping.tasks import load_election_stats

        city = cast(City, CityFactory(code="9999"))

        with patch("scraping.tasks.elections.load_stations", return_value=_den_haag_stations()):
            load_election_stats(city.pk)

        city.refresh_from_db()
        assert city.election_stats is None
        assert city.election_stats_fetched_at is None

    def test_no_op_for_missing_city(self):
        from scraping.tasks import load_election_stats

        with patch("scraping.tasks.elections.load_stations") as mock_load:
            load_election_stats(999999)

        mock_load.assert_not_called()

    def test_preserves_other_election_keys(self):
        from scraping.tasks import load_election_stats

        city = cast(City, CityFactory(code="0518", election_stats={"gr2026": {"totalVotes": 1}}))
        NeighborhoodFactory(code="BU05180001", city=city, geometry=SQUARE_A)

        with patch("scraping.tasks.elections.load_stations", return_value=_den_haag_stations()):
            load_election_stats(city.pk)

        city.refresh_from_db()
        assert (city.election_stats or {})["gr2026"] == {"totalVotes": 1}
        assert (city.election_stats or {})["tk2025"]["totalVotes"] == 20


class TestLoadStations:
    def test_downloads_parses_and_joins(self, tmp_path):
        rows = [
            [
                "GemeenteCode",
                "GemeenteNaam",
                "Postcode",
                "StembureauNaam",
                "StembureauCode",
                "PartijNaam",
                "AantalStemmen",
            ],
            ["518", "'s-Gravenhage", "2566AW", "Stembureau X", "SB1", "D66", "12"],
        ]
        buf = io.StringIO()
        csv.writer(buf, delimiter=";").writerows(rows)
        with zipfile.ZipFile(tmp_path / "tk2025_kiesraad_csv.zip", "w") as zf:
            zf.writestr(elections.VOTES_CSV_NAME, buf.getvalue())
        with (tmp_path / "tk2025_stemlokalen.csv").open("w") as f:
            writer = csv.writer(f)
            writer.writerow(["CBS gemeentecode", "Nummer stembureau", "Latitude", "Longitude"])
            writer.writerow(["GM0518", "1", "0.5", "0.5"])

        stations = elections.load_stations(tmp_path)

        assert stations["0518"][1].votes == {"D66": 12}
        assert (stations["0518"][1].lon, stations["0518"][1].lat) == (0.5, 0.5)


@pytest.mark.django_db
class TestFetchElectionStatsAdminAction:
    def test_dispatches_task_per_city(self, admin_client):
        c1 = cast(City, CityFactory())
        c2 = cast(City, CityFactory())
        with patch("scraping.admin.load_election_stats.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_election_stats", "_selected_action": [c1.pk, c2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(c1.pk)
        mock_delay.assert_any_call(c2.pk)


@pytest.mark.django_db
class TestElectionStatsInApi:
    def test_neighborhood_stats_merge_election_data(self, client):
        city = cast(City, CityFactory(code="0518"))
        NeighborhoodFactory(
            code="BU05180001",
            city=city,
            stats={"AantalInwoners_5": 6285},
            stats_year=2023,
            election_stats={
                "tk2025": {"totalVotes": 20, "stationCount": 1, "source": "buurt", "parties": {"D66": 12, "VVD": 8}}
            },
        )

        response = client.get("/v1/stats/neighborhoods", {"city": "0518"})

        assert response.status_code == 200
        stats = response.json()[0]["stats"]
        assert stats["AantalInwoners_5"] == 6285
        assert stats["tk2025"]["parties"]["D66"] == 12

    def test_election_data_without_cbs_stats(self, client):
        city = cast(City, CityFactory(code="0518"))
        NeighborhoodFactory(code="BU05180001", city=city, stats=None, election_stats={"tk2025": {"totalVotes": 5}})

        response = client.get("/v1/stats/neighborhoods", {"city": "0518"})

        assert response.json()[0]["stats"] == {"tk2025": {"totalVotes": 5}}

    def test_stats_stay_null_without_any_data(self, client):
        city = cast(City, CityFactory(code="0518"))
        NeighborhoodFactory(code="BU05180001", city=city, stats=None, election_stats=None)

        response = client.get("/v1/stats/neighborhoods", {"city": "0518"})

        assert response.json()[0]["stats"] is None

    def test_city_and_district_stats_merge_election_data(self, client):
        city = cast(City, CityFactory(code="0518", stats={"a": 1}, election_stats={"tk2025": {"totalVotes": 9}}))
        DistrictFactory(code="WK051801", city=city, stats=None, election_stats={"tk2025": {"totalVotes": 4}})

        city_resp = client.get("/v1/stats/cities/0518")
        district_resp = client.get("/v1/stats/districts", {"city": "0518"})

        assert city_resp.json()["stats"] == {"a": 1, "tk2025": {"totalVotes": 9}}
        assert district_resp.json()[0]["stats"] == {"tk2025": {"totalVotes": 4}}
