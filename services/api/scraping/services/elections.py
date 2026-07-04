"""ETL for election results per neighborhood (Tweede Kamer 2025).

Combines two CC0 open-data sources into per-buurt vote aggregates:

1. Kiesraad — votes per party per polling station (stembureau):
   https://data.overheid.nl/dataset/verkiezingsuitslag-tweede-kamer-2025
2. Open State Foundation "Waar is mijn stemlokaal" — polling station
   locations (lat/lon): https://waarismijnstemlokaal.nl/data

Stations are joined on (CBS gemeentecode, stembureau number), then assigned
to a buurt by point-in-polygon against `Neighborhood.geometry` (the CBS/PDOK
shapes already in the database). A station that falls outside every buurt
polygon (generalized shapes lose detail near boundaries) is assigned to the
nearest buurt. Buurten without any station inherit their wijk's aggregate,
flagged with ``"source": "wijk"``.

Voters may vote at any station in their gemeente, so buurt aggregates
approximate the leanings of a station's surroundings — they are not exact
residence-based results.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from loguru import logger

ELECTION_KEY = "tk2025"

VOTES_URL = (
    "https://data.overheid.nl/sites/default/files/dataset/"
    "a16f3352-c9ce-4831-a314-f989d442a258/resources/"
    "Verkiezingsuitslag%20Tweede%20Kamer%202025%20%28CSV%20Formaat%29.zip"
)
VOTES_SHA256 = "ffd9b0dbb61ff084577d809cffe40e66b4a42aff34723bd19d77794f3d0a83f5"
VOTES_CSV_NAME = "TK2025_Stemmen_Per_Lijst_Per_Stembureau.csv"

LOCATIONS_URL = "https://data.waarismijnstemlokaal.nl/datastore/dump/d4c0fa98-22d7-43fb-a80d-fd2f112a6627"
LOCATIONS_SHA256 = "3980d372e50b331b1bcb0bf6960b0d6f9c93b7edb5a84ee5b90df030acfbfa30"


@dataclass
class Station:
    """One polling station: its votes and, when known, its location."""

    gemeente_code: str  # zero-padded, e.g. "0518"
    number: int
    votes: dict[str, int] = field(default_factory=dict)
    lon: float | None = None
    lat: float | None = None

    @property
    def total(self) -> int:
        return sum(self.votes.values())


@dataclass
class Aggregate:
    votes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    station_count: int = 0

    def add(self, station: Station) -> None:
        for party, count in station.votes.items():
            self.votes[party] += count
        self.station_count += 1

    def to_stats(self, source: str) -> dict:
        parties = dict(sorted(self.votes.items(), key=lambda kv: (-kv[1], kv[0])))
        return {
            "totalVotes": sum(parties.values()),
            "stationCount": self.station_count,
            "source": source,
            "parties": parties,
        }


# --- Download ---


def _download(url: str, dest: Path, expected_sha256: str) -> Path:
    if not dest.exists():
        logger.info("Downloading {} -> {}", url, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != expected_sha256:
        logger.warning(
            "Checksum mismatch for {} (got {}, pinned {}); the publisher may have re-uploaded the file",
            dest.name,
            digest,
            expected_sha256,
        )
    return dest


def download_sources(cache_dir: Path) -> tuple[Path, Path]:
    """Fetch both source files into ``cache_dir`` (skipped when present)."""
    votes_zip = _download(VOTES_URL, cache_dir / "tk2025_kiesraad_csv.zip", VOTES_SHA256)
    locations_csv = _download(LOCATIONS_URL, cache_dir / "tk2025_stemlokalen.csv", LOCATIONS_SHA256)
    return votes_zip, locations_csv


# --- Parse ---


def _normalize_gemeente_code(raw: str) -> str:
    return raw.strip().removeprefix("GM").zfill(4)


def parse_votes(votes_zip: Path) -> dict[str, dict[int, Station]]:
    """Read the Kiesraad zip into ``{gemeente_code: {station_number: Station}}``."""
    stations: dict[str, dict[int, Station]] = defaultdict(dict)
    with zipfile.ZipFile(votes_zip) as zf, zf.open(VOTES_CSV_NAME) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"), delimiter=";")
        for row in reader:
            gemeente = _normalize_gemeente_code(row["GemeenteCode"])
            number = int(row["StembureauCode"].removeprefix("SB"))
            station = stations[gemeente].get(number)
            if station is None:
                station = stations[gemeente][number] = Station(gemeente_code=gemeente, number=number)
            station.votes[row["PartijNaam"]] = station.votes.get(row["PartijNaam"], 0) + int(row["AantalStemmen"])
    return dict(stations)


def parse_locations(locations_csv: Path) -> dict[tuple[str, int], tuple[float, float]]:
    """Read the stemlokaal dump into ``{(gemeente_code, number): (lon, lat)}``."""
    locations: dict[tuple[str, int], tuple[float, float]] = {}
    with locations_csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                gemeente = _normalize_gemeente_code(row["CBS gemeentecode"])
                number = int(float(row["Nummer stembureau"]))
                lon, lat = float(row["Longitude"]), float(row["Latitude"])
            except KeyError, ValueError:
                continue
            locations[(gemeente, number)] = (lon, lat)
    return locations


# --- Geometry ---
# `Neighborhood.geometry` is a list of polygons; each polygon is a list of
# rings (first exterior, rest holes); each ring is a list of [lon, lat].


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: list) -> bool:
    for polygon in geometry:
        if not polygon:
            continue
        if _point_in_ring(lon, lat, polygon[0]) and not any(_point_in_ring(lon, lat, hole) for hole in polygon[1:]):
            return True
    return False


def _segment_distance_sq(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def distance_sq_to_geometry(lon: float, lat: float, geometry: list) -> float:
    best = float("inf")
    for polygon in geometry:
        for ring in polygon:
            j = len(ring) - 1
            for i in range(len(ring)):
                best = min(best, _segment_distance_sq(lon, lat, *ring[i], *ring[j]))
                j = i
    return best


# --- Assignment & aggregation ---


@dataclass
class CityElectionStats:
    """Election aggregates for one gemeente, keyed by CBS code."""

    city: dict
    districts: dict[str, dict]
    neighborhoods: dict[str, dict]
    located_stations: int
    total_stations: int
    fallback_neighborhoods: int
    empty_neighborhoods: int


def aggregate_city(
    stations: dict[int, Station],
    neighborhoods: list,  # Neighborhood-like: .code, .district_id/.district, .geometry
) -> CityElectionStats:
    """Assign located stations to buurten and roll up buurt/wijk/gemeente stats.

    The gemeente aggregate includes *all* stations (also unlocated ones such
    as postal-vote bureaus), so it matches the official municipal totals.
    """
    with_geometry = [n for n in neighborhoods if n.geometry]

    city_agg = Aggregate()
    buurt_aggs: dict[str, Aggregate] = defaultdict(Aggregate)
    district_aggs: dict[str, Aggregate] = defaultdict(Aggregate)
    district_of = {n.code: n.district.code if n.district else None for n in neighborhoods}

    located = 0
    for station in stations.values():
        city_agg.add(station)
        lon, lat = station.lon, station.lat
        if lon is None or lat is None or not with_geometry:
            continue
        located += 1
        home = next(
            (n for n in with_geometry if point_in_geometry(lon, lat, n.geometry)),
            None,
        )
        if home is None:
            home = min(
                with_geometry,
                key=lambda n: distance_sq_to_geometry(lon, lat, n.geometry),
            )
        buurt_aggs[home.code].add(station)
        home_district = district_of[home.code]
        if home_district:
            district_aggs[home_district].add(station)

    neighborhood_stats: dict[str, dict] = {}
    fallback = empty = 0
    for n in neighborhoods:
        district_code = district_of[n.code]
        if n.code in buurt_aggs:
            neighborhood_stats[n.code] = buurt_aggs[n.code].to_stats("buurt")
        elif district_code and district_code in district_aggs:
            neighborhood_stats[n.code] = district_aggs[district_code].to_stats("wijk")
            fallback += 1
        else:
            empty += 1

    return CityElectionStats(
        city=city_agg.to_stats("gemeente"),
        districts={code: agg.to_stats("wijk") for code, agg in district_aggs.items()},
        neighborhoods=neighborhood_stats,
        located_stations=located,
        total_stations=len(stations),
        fallback_neighborhoods=fallback,
        empty_neighborhoods=empty,
    )


def attach_locations(
    stations: dict[str, dict[int, Station]],
    locations: dict[tuple[str, int], tuple[float, float]],
) -> None:
    """Fill in lon/lat on every station that has a known location."""
    for gemeente, by_number in stations.items():
        for number, station in by_number.items():
            location = locations.get((gemeente, number))
            if location is not None:
                station.lon, station.lat = location
