from __future__ import annotations

from applicationhelper.agents.region_profiles import DACH_BOARDS, resolve_region_boards
from applicationhelper.models.job import ATSPlatform


def test_resolve_region_boards_case_and_whitespace_insensitive():
    assert resolve_region_boards("DACH") == DACH_BOARDS
    assert resolve_region_boards(" dach ") == DACH_BOARDS
    assert resolve_region_boards("Germany") == DACH_BOARDS
    assert resolve_region_boards("de") == DACH_BOARDS


def test_resolve_region_boards_unknown_region_returns_empty():
    assert resolve_region_boards("mars") == []


def test_dach_boards_have_required_extra_fields_for_their_platform():
    for board in DACH_BOARDS:
        if board.platform == ATSPlatform.WORKDAY:
            assert "dc" in board.extra and "site" in board.extra
