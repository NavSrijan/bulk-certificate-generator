import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
import app.database as app_db
import app.services.job_service as job_service_module
from app.main import app


@pytest.fixture(scope="session")
def temp_storage():
    """Create a temporary storage directory for tests and clean up afterwards."""
    temp_dir = tempfile.mkdtemp(prefix="cert_test_storage_")
    old_storage = settings.STORAGE_DIR
    old_zip_storage = settings.ZIP_STORAGE_DIR

    test_storage_dir = Path(temp_dir) / "certificates"
    test_zip_dir = Path(temp_dir) / "zips"
    test_storage_dir.mkdir(parents=True, exist_ok=True)
    test_zip_dir.mkdir(parents=True, exist_ok=True)

    settings.STORAGE_DIR = str(test_storage_dir)
    settings.ZIP_STORAGE_DIR = str(test_zip_dir)

    yield {
        "root": temp_dir,
        "storage": str(test_storage_dir),
        "zips": str(test_zip_dir),
    }

    settings.STORAGE_DIR = old_storage
    settings.ZIP_STORAGE_DIR = old_zip_storage
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def db_session(temp_storage):
    """Create an isolated SQLite database file per test function."""
    db_file = Path(temp_storage["root"]) / f"test_{tempfile.mktemp(prefix='')[-6:]}.db"
    test_db_url = f"sqlite:///{db_file}"

    test_engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Bind tables
    Base.metadata.create_all(bind=test_engine)

    # Override app_db and job_service_module SessionLocal
    orig_session_local = app_db.SessionLocal
    app_db.SessionLocal = TestingSessionLocal
    job_service_module.SessionLocal = TestingSessionLocal

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app_db.SessionLocal = orig_session_local
        job_service_module.SessionLocal = orig_session_local
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        if db_file.exists():
            db_file.unlink()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
