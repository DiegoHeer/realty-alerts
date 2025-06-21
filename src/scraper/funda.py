import json
from collections.abc import Sequence
from enum import StrEnum
from urllib.parse import quote, urlencode

from enums import Websites
from scraper.base import BaseScraper


class FundaScraper(BaseScraper):
    website = Websites.FUNDA
    base_url = "https://www.funda.nl/zoeken/koop"

    def build_query_url(self) -> str:
        query_dicts = filter(
            None,
            [
                self._build_list_query("object_type", self.filter.house_types),
                self._build_list_query("energy_label", self.filter.energy_labels),
                self._build_list_query("construction_type", self.filter.construction_types),
                self._build_list_query("construction_period", self.filter.construction_periods),
                self._build_range_query("price", self.filter.min_price, self.filter.max_price),
                self._build_range_query("floor_area", self.filter.min_floor_area, self.filter.max_floor_area),
                self._build_range_query("rooms", self.filter.min_rooms, self.filter.max_rooms),
                self._build_range_query("bedrooms", self.filter.min_bedrooms, self.filter.max_bedrooms),
            ],
        )

        params = {key: value for query_dict in query_dicts for key, value in query_dict.items()}
        encoded_params = urlencode(params, doseq=True, quote_via=quote)

        return f"{self.base_url}?{encoded_params}"

    @staticmethod
    def _build_list_query(param: str, items: Sequence[StrEnum] | None) -> dict[str, str] | None:
        if not items:
            return None

        values = list({item.value for item in items})
        values.sort()
        return {param: json.dumps(values)}

    @staticmethod
    def _build_range_query(param: str, min_value: int | None, max_value: int | None) -> dict[str, str] | None:
        if min_value is None and max_value is None:
            return None

        range_value = f"{min_value or ''}-{max_value or ''}"
        return {param: json.dumps(range_value)}
