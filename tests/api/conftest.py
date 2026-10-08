from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.documents import make_document, make_glossary
from tests.support.index import build_test_index
from tests.support.web import NPT, make_client, make_settings
from wellscope.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    index = build_test_index(settings.database_path, [make_document()], make_glossary(NPT))
    with make_client(settings, index) as test_client:
        yield test_client
