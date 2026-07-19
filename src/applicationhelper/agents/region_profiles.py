"""Hardcoded default board lists per macro-region.

Used by JobSearchAgent when `SearchFilters.region` is set and `ats_boards` is
empty, so callers can say "search Germany" without hand-listing board tokens.

Every board below was verified live (see ats_clients module docstrings for
per-platform verification notes) as of 2026-07-19. This list is intentionally
small and will need to grow as more DACH company boards get verified —
resist the temptation to add guessed board tokens here without testing them
first (Lever and SAP SuccessFactors both looked plausible and turned out not
to have a usable public API).
"""

from __future__ import annotations

from applicationhelper.models.filters import ATSBoardTarget
from applicationhelper.models.job import ATSPlatform

DACH_BOARDS: list[ATSBoardTarget] = [
    ATSBoardTarget(
        platform=ATSPlatform.SMARTRECRUITERS,
        board_token="BoschGroup",
        company_name="Bosch",
        extra={"country": "de"},
    ),
    ATSBoardTarget(
        platform=ATSPlatform.WORKDAY,
        board_token="db",
        company_name="Deutsche Bank",
        extra={"dc": "wd3", "site": "DBWebsite"},
    ),
]

# Board companies operate globally, so picking their board isn't enough to
# scope results to the region — this location-text filter (matched against
# JobPosting.location by JobSearchAgent._passes_filters) is what actually
# excludes e.g. a Deutsche Bank Pune listing from a "DACH" search.
DACH_LOCATIONS: list[str] = ["Germany", "Deutschland", "Austria", "Österreich", "Switzerland", "Schweiz"]

_REGION_PROFILES: dict[str, list[ATSBoardTarget]] = {
    "dach": DACH_BOARDS,
    "germany": DACH_BOARDS,
    "de": DACH_BOARDS,
}

_REGION_LOCATIONS: dict[str, list[str]] = {
    "dach": DACH_LOCATIONS,
    "germany": DACH_LOCATIONS,
    "de": DACH_LOCATIONS,
}


def resolve_region_boards(region: str) -> list[ATSBoardTarget]:
    return _REGION_PROFILES.get(region.strip().lower(), [])


def resolve_region_locations(region: str) -> list[str]:
    return _REGION_LOCATIONS.get(region.strip().lower(), [])
