"""
scripts/bootstrap_admin.py
==========================
Developer-only utility to promote the designated development account to the
``admin`` role in the AstroOS database.

SAFETY RESTRICTIONS
-------------------
- Refuses to run when ENVIRONMENT=production.
- Only promotes one explicitly configured email address.
- Never creates new users, API keys, or modifies authentication configuration.
- Never prints passwords, hashes, tokens, or any secret material.
- Uses the application's existing SQLAlchemy ORM and session configuration.
- Commits only after all safety validations pass; rolls back on any failure.
- Supports a ``--dry-run`` mode that inspects without committing any changes.

USAGE
-----
Dry-run (inspect only, no changes committed):
    python -m scripts.bootstrap_admin --dry-run

Perform the promotion:
    python -m scripts.bootstrap_admin
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so app.* imports resolve correctly
# when run as a top-level script (e.g. python scripts/bootstrap_admin.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The one and only development account that this script is authorised to
# promote.  Do NOT accept the target email via command-line argument to
# prevent accidental (or intentional) promotion of other accounts.
TARGET_EMAIL: str = "astrotest@example.com"
TARGET_ROLE: str = "admin"

EXIT_OK = 0
EXIT_ERROR = 1


# ---------------------------------------------------------------------------
# Core promotion logic (importable for testing)
# ---------------------------------------------------------------------------

def promote_to_admin(
    *,
    dry_run: bool = False,
    environment: str | None = None,
    db_session=None,
) -> tuple[bool, str]:
    """Attempt to promote ``TARGET_EMAIL`` to ``admin`` role.

    Args:
        dry_run:     When ``True``, inspect the account but do NOT commit.
        environment: Override ENVIRONMENT value (used in tests).
        db_session:  Injectable SQLAlchemy session (used in tests).

    Returns:
        ``(success: bool, message: str)``

    This function does NOT exit the process; it returns a structured result
    so it can be called from tests without side-effects.
    """
    # ------------------------------------------------------------------
    # 1. Refuse to run in production
    # ------------------------------------------------------------------
    if environment is None:
        from app.core.config import ENVIRONMENT
        environment = ENVIRONMENT

    if environment == "production":
        return False, (
            "ABORTED: This script must not run in a production environment. "
            "Set ENVIRONMENT=production is detected. Exiting safely."
        )

    # ------------------------------------------------------------------
    # 2. Acquire a database session
    # ------------------------------------------------------------------
    session_owned = False
    if db_session is None:
        from app.db.session import SessionLocal
        db_session = SessionLocal()
        session_owned = True

    try:
        from app.models.user import User

        # ------------------------------------------------------------------
        # 3. Look up the target account (normalise email as the model does)
        # ------------------------------------------------------------------
        normalized_email = TARGET_EMAIL.strip().lower()
        user: User | None = (
            db_session.query(User)
            .filter(User.email == normalized_email)
            .first()
        )

        if user is None:
            return False, (
                f"ABORTED: Account '{normalized_email}' was not found in the "
                "database. No changes were made."
            )

        # ------------------------------------------------------------------
        # 4. Require the account to be active
        # ------------------------------------------------------------------
        if not user.is_active:
            return False, (
                f"ABORTED: Account '{normalized_email}' is inactive. "
                "Re-activate the account before promoting it. No changes were made."
            )

        # ------------------------------------------------------------------
        # 5. Short-circuit if already the target role
        # ------------------------------------------------------------------
        if user.role == TARGET_ROLE:
            return True, (
                f"INFO: Account '{normalized_email}' already has role "
                f"'{TARGET_ROLE}'. No changes necessary."
            )

        original_role = user.role

        if dry_run:
            return True, (
                f"DRY-RUN: Account '{normalized_email}' is eligible for "
                f"promotion from '{original_role}' to '{TARGET_ROLE}'. "
                "No changes were committed."
            )

        # ------------------------------------------------------------------
        # 6. Perform the promotion
        # ------------------------------------------------------------------
        user.role = TARGET_ROLE

        try:
            db_session.commit()
        except Exception as exc:
            db_session.rollback()
            return False, (
                f"ERROR: Database commit failed. Transaction rolled back. "
                f"Reason: {type(exc).__name__}: {exc}"
            )

        return True, (
            f"SUCCESS: Account '{normalized_email}' promoted from "
            f"'{original_role}' to '{TARGET_ROLE}'."
        )

    finally:
        if session_owned:
            db_session.close()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bootstrap_admin",
        description=(
            "Developer utility: promote the designated AstroOS development "
            "account to the admin role.\n\n"
            f"Target account: {TARGET_EMAIL}\n\n"
            "WARNING: This script must not be run in production environments."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Inspect the target account and report whether promotion is "
            "possible without committing any changes to the database."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    success, message = promote_to_admin(dry_run=args.dry_run)
    print(message)
    return EXIT_OK if success else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

