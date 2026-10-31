"""
tests/test_bootstrap_admin.py
==============================
Unit tests for scripts/bootstrap_admin.py.

All tests run in an isolated SQLAlchemy transaction that is rolled back after
each test, so the development database is never modified.

Scenarios covered:
1. Existing active user is successfully promoted.
2. Missing user — returns failure with informative message.
3. Inactive user — returns failure; account not promoted.
4. Production environment — script is rejected before any DB access.
5. Dry-run — reports eligibility but does NOT commit the role change.
6. Already admin — idempotent; reports that no change is necessary.
7. Rollback on commit failure — role change is NOT persisted when commit raises.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.core.security import hash_password
from app.models.user import User
from scripts.bootstrap_admin import TARGET_EMAIL, TARGET_ROLE, promote_to_admin


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_user(
    db,
    email: str = TARGET_EMAIL,
    role: str = "user",
    is_active: bool = True,
) -> User:
    """Create and flush (not commit) a User inside the current transaction."""
    user = User(
        email=email,
        hashed_password=hash_password("BootstrapTest1!"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()  # Assigns PK; rollback will undo this.
    return user


# ---------------------------------------------------------------------------
# 1. Successful promotion of an existing active user
# ---------------------------------------------------------------------------

def test_existing_active_user_is_promoted(db):
    """A valid, active target user should be promoted to admin."""
    user = _make_user(db, role="user")
    assert user.role == "user"

    success, message = promote_to_admin(
        db_session=db,
        environment="development",
    )

    assert success is True
    assert "SUCCESS" in message
    assert TARGET_EMAIL in message
    assert TARGET_ROLE in message

    # Verify the ORM object reflects the updated role in the session.
    db.refresh(user)
    assert user.role == TARGET_ROLE


# ---------------------------------------------------------------------------
# 2. Missing user
# ---------------------------------------------------------------------------

def test_missing_user_returns_failure(db):
    """When the target account does not exist, the script must abort safely."""
    # Ensure no user with the target email exists in this transaction.
    success, message = promote_to_admin(
        db_session=db,
        environment="development",
    )

    assert success is False
    assert "not found" in message.lower() or "ABORTED" in message


# ---------------------------------------------------------------------------
# 3. Inactive user
# ---------------------------------------------------------------------------

def test_inactive_user_is_rejected(db):
    """An inactive target account must not be promoted."""
    _make_user(db, role="user", is_active=False)

    success, message = promote_to_admin(
        db_session=db,
        environment="development",
    )

    assert success is False
    assert "inactive" in message.lower()
    assert "ABORTED" in message


# ---------------------------------------------------------------------------
# 4. Production environment rejection
# ---------------------------------------------------------------------------

def test_production_environment_is_rejected(db):
    """The script must refuse to operate when ENVIRONMENT=production."""
    # We do NOT need a user in the DB; rejection happens before any DB access.
    success, message = promote_to_admin(
        db_session=db,
        environment="production",
    )

    assert success is False
    assert "production" in message.lower()
    assert "ABORTED" in message


# ---------------------------------------------------------------------------
# 5. Dry-run does not modify the role
# ---------------------------------------------------------------------------

def test_dry_run_does_not_commit_role_change(db):
    """--dry-run must report eligibility but must NOT persist any change."""
    user = _make_user(db, role="user")
    original_role = user.role

    success, message = promote_to_admin(
        db_session=db,
        environment="development",
        dry_run=True,
    )

    assert success is True
    assert "DRY-RUN" in message
    assert "eligible" in message.lower()

    # The in-session object must be unmodified.
    db.refresh(user)
    assert user.role == original_role


# ---------------------------------------------------------------------------
# 6. Already admin — idempotent
# ---------------------------------------------------------------------------

def test_already_admin_is_idempotent(db):
    """If the account is already admin the script reports success without change."""
    user = _make_user(db, role="admin")

    success, message = promote_to_admin(
        db_session=db,
        environment="development",
    )

    assert success is True
    assert "already" in message.lower()

    db.refresh(user)
    assert user.role == "admin"


# ---------------------------------------------------------------------------
# 7. Rollback on commit failure
# ---------------------------------------------------------------------------

def test_rollback_on_commit_failure(db):
    """When the DB commit raises an exception the role change is rolled back."""
    user = _make_user(db, role="user")

    # Patch db.commit to raise and db.rollback to track the call.
    rollback_called = []

    original_commit = db.commit
    original_rollback = db.rollback

    def failing_commit():
        raise RuntimeError("Simulated commit failure")

    def tracking_rollback():
        rollback_called.append(True)
        original_rollback()

    db.commit = failing_commit
    db.rollback = tracking_rollback

    try:
        success, message = promote_to_admin(
            db_session=db,
            environment="development",
        )
    finally:
        # Restore real methods so the test-level transaction can roll back.
        db.commit = original_commit
        db.rollback = original_rollback

    assert success is False
    assert "ERROR" in message
    assert "rolled back" in message.lower()
    assert rollback_called, "db.rollback() was never called after commit failure"


# ---------------------------------------------------------------------------
# 8. Dry-run on non-existent user returns failure (not confusing success)
# ---------------------------------------------------------------------------

def test_dry_run_missing_user_returns_failure(db):
    """--dry-run for a missing user must still return failure."""
    success, message = promote_to_admin(
        db_session=db,
        environment="development",
        dry_run=True,
    )

    assert success is False
    assert "not found" in message.lower() or "ABORTED" in message


# ---------------------------------------------------------------------------
# 9. Dry-run on inactive user returns failure
# ---------------------------------------------------------------------------

def test_dry_run_inactive_user_returns_failure(db):
    """--dry-run must not report eligibility for an inactive account."""
    _make_user(db, role="user", is_active=False)

    success, message = promote_to_admin(
        db_session=db,
        environment="development",
        dry_run=True,
    )

    assert success is False
    assert "inactive" in message.lower()

