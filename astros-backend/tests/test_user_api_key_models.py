"""
tests/test_user_api_key_models.py
=================================
Unit and integration tests for User and ApiKey SQLAlchemy models (Phase 5B.2).

Verifies schema constraints, validation hooks, relationships, default values,
unique constraints, cascades, and security protections using the test database.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_key import ApiKey
from app.models.user import User


# ===========================================================================
# 1. User Model Tests
# ===========================================================================
class TestUserModel:
    def test_successful_user_creation(self, db):
        user = User(
            email="astronomer@example.com",
            hashed_password="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
            full_name="Galileo Galilei",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert isinstance(user.id, uuid.UUID)
        assert user.email == "astronomer@example.com"
        assert user.full_name == "Galileo Galilei"
        assert user.role == "user"
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.created_at.tzinfo is not None

    def test_email_normalization_on_assignment(self, db):
        user = User(
            email="  JoHn.DoE@ExAmPlE.CoM  ",
            hashed_password="somehashvalue123",
        )
        assert user.email == "john.doe@example.com"

        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.email == "john.doe@example.com"

    def test_invalid_empty_email_rejected_by_validator(self):
        with pytest.raises(ValueError, match="Email cannot be blank"):
            User(email="   ", hashed_password="somehashvalue123")

        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            User(email=None, hashed_password="somehashvalue123")

    def test_unique_email_enforcement(self, db):
        user1 = User(
            email="unique@example.com",
            hashed_password="hash1",
        )
        db.add(user1)
        db.commit()

        user2 = User(
            email="UNIQUE@example.com",  # Normalizes to identical unique@example.com
            hashed_password="hash2",
        )
        db.add(user2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_default_role_is_user(self, db):
        user = User(
            email="defaultrole@example.com",
            hashed_password="somehashvalue123",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.role == "user"

    def test_default_is_active_is_true(self, db):
        user = User(
            email="isactive@example.com",
            hashed_password="somehashvalue123",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.is_active is True

    def test_required_fields_enforced(self, db):
        # Missing hashed_password
        user_no_pw = User(email="nopw@example.com")
        db.add(user_no_pw)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_invalid_role_rejected_by_check_constraint(self, db):
        user_bad_role = User(
            email="badrole@example.com",
            hashed_password="hash",
            role="superadmin",  # not in ('user', 'admin', 'service')
        )
        db.add(user_bad_role)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_admin_and_service_roles_allowed(self, db):
        admin_user = User(
            email="admin@example.com",
            hashed_password="hash",
            role="admin",
        )
        service_user = User(
            email="service@example.com",
            hashed_password="hash",
            role="service",
        )
        db.add_all([admin_user, service_user])
        db.commit()

        db.refresh(admin_user)
        db.refresh(service_user)
        assert admin_user.role == "admin"
        assert service_user.role == "service"


# ===========================================================================
# 2. API-Key Model Tests
# ===========================================================================
class TestApiKeyModel:
    def test_successful_api_key_creation(self, db):
        user = User(
            email="apikeyowner@example.com",
            hashed_password="hash",
        )
        db.add(user)
        db.commit()

        # Simulate generating a key and storing its SHA-256 hash
        raw_key = "ast_live_" + "x" * 32
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]

        api_key = ApiKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name="Production Ingestion Agent",
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        assert isinstance(api_key.id, uuid.UUID)
        assert api_key.user_id == user.id
        assert api_key.key_hash == key_hash
        assert api_key.key_prefix == key_prefix
        assert api_key.name == "Production Ingestion Agent"
        assert api_key.is_active is True
        assert api_key.expires_at is not None
        assert api_key.created_at is not None
        assert api_key.user.id == user.id

    def test_unique_key_hash_enforcement(self, db):
        user = User(email="hashdup@example.com", hashed_password="hash")
        db.add(user)
        db.commit()

        shared_hash = hashlib.sha256(b"same_key").hexdigest()

        key1 = ApiKey(
            user_id=user.id,
            key_hash=shared_hash,
            key_prefix="ast_live_1234",
            name="Key 1",
        )
        db.add(key1)
        db.commit()

        key2 = ApiKey(
            user_id=user.id,
            key_hash=shared_hash,
            key_prefix="ast_live_1234",
            name="Key 2",
        )
        db.add(key2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_user_api_key_relationship_and_cascade_delete(self, db):
        user = User(email="cascade@example.com", hashed_password="hash")
        db.add(user)
        db.commit()

        key = ApiKey(
            user_id=user.id,
            key_hash=hashlib.sha256(b"cascade_key").hexdigest(),
            key_prefix="ast_live_casc",
            name="Cascade Key",
        )
        db.add(key)
        db.commit()
        key_id = key.id

        # Verify relationship from user side
        db.refresh(user)
        assert len(user.api_keys) == 1
        assert user.api_keys[0].id == key_id

        # Delete user -> ApiKey must be cascade deleted
        db.delete(user)
        db.commit()

        remaining_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        assert remaining_key is None

    def test_api_key_expiration_and_revocation(self, db):
        user = User(email="revocation@example.com", hashed_password="hash")
        db.add(user)
        db.commit()

        past_time = datetime.now(timezone.utc) - timedelta(days=1)
        expired_key = ApiKey(
            user_id=user.id,
            key_hash=hashlib.sha256(b"expired").hexdigest(),
            key_prefix="ast_exp_",
            name="Expired Key",
            expires_at=past_time,
            is_active=True,
        )
        revoked_key = ApiKey(
            user_id=user.id,
            key_hash=hashlib.sha256(b"revoked").hexdigest(),
            key_prefix="ast_rev_",
            name="Revoked Key",
            is_active=False,
        )
        db.add_all([expired_key, revoked_key])
        db.commit()

        db.refresh(expired_key)
        db.refresh(revoked_key)

        assert expired_key.expires_at < datetime.now(timezone.utc)
        assert revoked_key.is_active is False


# ===========================================================================
# 3. Security Assertions
# ===========================================================================
class TestSecurityGuarantees:
    def test_plaintext_password_is_not_stored_as_attribute(self):
        """User model only possesses 'hashed_password', never a plaintext password attribute."""
        user = User(
            email="sec@example.com",
            hashed_password="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        )
        assert not hasattr(user, "password")
        assert not hasattr(user, "plain_password")
        assert hasattr(user, "hashed_password")
        assert user.hashed_password.startswith("$argon2id$")

    def test_plaintext_api_key_is_not_stored(self):
        """ApiKey model only possesses 'key_hash' (SHA-256) and 'key_prefix'."""
        key = ApiKey(
            user_id=uuid.uuid4(),
            key_hash=hashlib.sha256(b"raw_token").hexdigest(),
            key_prefix="ast_live_1234",
            name="Agent",
        )
        assert not hasattr(key, "key")
        assert not hasattr(key, "raw_key")
        assert not hasattr(key, "token")
        assert len(key.key_hash) == 64  # SHA-256 hex string

    def test_public_user_registration_defaults_cannot_grant_admin(self, db):
        """A user constructed with default arguments always receives the 'user' role."""
        user = User(
            email="publicregistrant@example.com",
            hashed_password="somehashvalue123",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.role == "user"
        assert user.role != "admin"
        assert user.role != "service"

