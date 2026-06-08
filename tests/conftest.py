from __future__ import annotations

import sys
import hashlib
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path and resolve sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.database

# Setup test DB paths
TEST_DB_PATH = ROOT / "database" / "test_quanlylophoc.sqlite3"
HASH_FILE_PATH = ROOT / "database" / ".models_hash"
MODELS_FILE_PATH = ROOT / "app" / "models.py"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Global test engine and TestingSessionLocal template
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Overwrite app.database globally immediately to intercept all database connections
app.database.DATABASE_URL = TEST_DATABASE_URL
app.database.engine = test_engine
app.database.SessionLocal = TestingSessionLocal

# Import other components now that the database has been overridden
from app.database import Base, get_db, init_db
from app.main import app as fastapi_app
from app.seeder.seed import seed_sample_data
from fastapi.testclient import TestClient

def pytest_addoption(parser):
    """Thêm flag --reset-db vào pytest CLI"""
    parser.addoption(
        "--reset-db", action="store_true", default=False, help="Force recreate the test database and re-seed"
    )

def get_file_hash(filepath: Path) -> str:
    """Tính MD5 của file models.py để nhận biết thay đổi Database Schema"""
    if not filepath.exists():
        return ""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

@pytest.fixture(scope="session", autouse=True)
def setup_test_database(request):
    """
    Fixture này chạy 1 lần duy nhất khi bắt đầu chạy toàn bộ test (scope="session").
    Nó quyết định việc có cần XÓA TRẮNG DB và SEED lại hay không.
    """
    force_reset = request.config.getoption("--reset-db")
    current_hash = get_file_hash(MODELS_FILE_PATH)
    
    saved_hash = ""
    if HASH_FILE_PATH.exists():
        with open(HASH_FILE_PATH, "r") as f:
            saved_hash = f.read().strip()

    db_exists = TEST_DB_PATH.exists()
    schema_changed = current_hash != saved_hash

    if force_reset or not db_exists or schema_changed:
        print("\n[Test Setup] Model structure changed or reset requested. Recreating database...")
        # Drop old DB if it exists
        Base.metadata.drop_all(bind=test_engine)
        # Create tables and run app migrations/logic
        init_db()
        
        # Chạy Seeder
        seed_sample_data()

        # Save the new hash
        with open(HASH_FILE_PATH, "w") as f:
            f.write(current_hash)
        print("[Test Setup] Completed creating and seeding test database.")
    else:
        print("\n[Test Setup] Reusing cached test database (no schema changes).")

@pytest.fixture(scope="function", autouse=True)
def force_db_rollback():
    """
    Fixture này chạy tự động cho mọi test function.
    Nó tạo 1 transaction và tự động rollback sau khi test kết thúc,
    đảm bảo trạng thái database luôn sạch sẽ.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    
    # Tạo sessionmaker gắn với connection hiện tại
    session = TestingSessionLocal(bind=connection)
    
    # Ghi đè dependency get_db của FastAPI
    def override_get_db():
        try:
            yield session
        finally:
            pass
            
    fastapi_app.dependency_overrides[get_db] = override_get_db
    
    # Ghi đè SessionLocal của app.database
    original_session_local = app.database.SessionLocal
    def session_factory(*args, **kwargs):
        return TestingSessionLocal(bind=connection, *args, **kwargs)
    app.database.SessionLocal = session_factory
    
    yield session
    
    # Rollback và khôi phục
    session.close()
    transaction.rollback()
    connection.close()
    
    app.database.SessionLocal = original_session_local
    fastapi_app.dependency_overrides.clear()
