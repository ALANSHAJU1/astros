
import hashlib
import os
from pathlib import Path
import uuid

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.celestial_event import CelestialEvent
from app.models.environmental_observation import EnvironmentalObservation
from app.models.visibility_assessment import VisibilityAssessment
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.refresh_token import RefreshToken


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@pytest.fixture(autouse=True)
def setup_default_jwt_secret(monkeypatch):
    """Ensure a valid 32-character secret is present during tests if unset."""
    secret = "t" * 32
    monkeypatch.setattr("app.core.config.JWT_SECRET_KEY", secret)
    monkeypatch.setattr("app.core.security.JWT_SECRET_KEY", secret)


@pytest.fixture(scope="session")
def test_engine():
    test_url = os.getenv("TEST_DATABASE_URL")

    if not test_url:
        pytest.fail("TEST_DATABASE_URL is missing from .env")

    # Create the engine before using it.
    engine = create_engine(test_url, pool_pre_ping=True)

    try:
        # Safety check: never run these tests against the development DB.
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            if database_name != "astros_test_db":
                pytest.fail(
                    "Safety check failed: expected astros_test_db, "
                    f"but connected to {database_name!r}"
                )

        # Create tables in foreign-key dependency order.
        CelestialEvent.__table__.create(engine, checkfirst=True)
        EnvironmentalObservation.__table__.create(
            engine, checkfirst=True
        )
        VisibilityAssessment.__table__.create(
            engine, checkfirst=True
        )
        User.__table__.create(engine, checkfirst=True)
        ApiKey.__table__.create(engine, checkfirst=True)
        RefreshToken.__table__.create(engine, checkfirst=True)

        yield engine

    finally:
        engine.dispose()


@pytest.fixture
def db(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()

    TestingSessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Create default test user with admin role so existing domain tests run seamlessly
    admin_user = User(
        email=f"default_client_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123!"),
        role="admin",
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    token = create_access_token(subject=admin_user.id, role="admin")

    try:
        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def anonymous_client(db):
    """TestClient without any authentication credentials."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_client(db):
    """TestClient with valid ordinary user credentials (role='user')."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    user = User(
        email=f"auth_user_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123!"),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, role="user")

    try:
        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_client(db):
    """TestClient with valid administrator credentials (role='admin')."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    admin = User(
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123!"),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    token = create_access_token(subject=admin.id, role="admin")

    try:
        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def service_client(db):
    """TestClient with valid service credentials (role='service' via X-API-Key)."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    service_user = User(
        email=f"service_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Password123!"),
        role="service",
        is_active=True,
    )
    db.add(service_user)
    db.commit()
    db.refresh(service_user)

    raw_key = f"ast_live_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = ApiKey(
        user_id=service_user.id,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        name="Test Service Client Key",
        is_active=True,
    )
    db.add(api_key)
    db.commit()

    try:
        with TestClient(app, headers={"X-API-Key": raw_key}) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


