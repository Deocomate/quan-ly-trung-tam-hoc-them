from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from app.database import engine, Base, init_db

@pytest.fixture(scope="session", autouse=True)
def clean_db():
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    init_db()

