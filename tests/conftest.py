from __future__ import annotations

import pytest

from applicationhelper.storage.db import make_engine, make_session_factory


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(tmp_path / "test.sqlite3")
    return make_session_factory(engine)


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s
