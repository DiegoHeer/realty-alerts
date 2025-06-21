from enum import StrEnum


class Websites(StrEnum):
    FUNDA = "funda"


class HouseTypes(StrEnum):
    WOONHUIS = "house"
    APPARTEMENT = "apartment"
    PARKEERGELEGENHEID = "parking"
    BOUWGROND = "land"


class EnergyLabel(StrEnum):
    A_FIVE_PLUS = "A+++++"
    A_FOUR_PLUS = "A++++"
    A_THREE_PLUS = "A+++"
    A_TWO_PLUS = "A++"
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class ConstructionType(StrEnum):
    NIEUWBOUW = "newly_built"
    BESTAANDE_BOUW = "resale"


class ConstructionPeriod(StrEnum):
    ONBEKEND = "unknown"
    BEFORE_1906 = "before_1906"
    FROM_1906_TO_1930 = "from_1906_to_1930"
    FROM_1931_TO_1944 = "from_1931_to_1944"
    FROM_1945_TO_1959 = "from_1945_to_1959"
    FROM_1960_TO_1970 = "from_1960_to_1970"
    FROM_1971_TO_1980 = "from_1971_to_1980"
    FROM_1981_TO_1990 = "from_1981_to_1990"
    FROM_1991_TO_2000 = "from_1991_to_2000"
    FROM_2001_TO_2010 = "from_2001_to_2010"
    FROM_2011_TO_2020 = "from_2011_to_2020"
    AFTER_2020 = "after_2020"


class QueryResultORMStatus(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    NOTIFIED = "notified"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.name, item.value) for item in list(cls)]

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in list(cls)]
