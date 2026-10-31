from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User


router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["Admin - User Management"],
)


# -------------------------
# Response and request schemas
# -------------------------

class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateRoleRequest(BaseModel):
    role: Literal["user", "admin"]


class UpdateStatusRequest(BaseModel):
    is_active: bool


# -------------------------
# Helpers
# -------------------------

def lock_admin_accounts(db: Session) -> list[User]:
    """Serialize admin role/status changes by locking current admin rows."""
    return (
        db.query(User)
        .filter(User.role == "admin")
        .order_by(User.id)
        .with_for_update()
        .all()
    )


def ensure_another_active_admin(
    db: Session,
    target_user: User,
) -> None:
    """Prevent removing the last active administrator."""
    if target_user.role != "admin" or not target_user.is_active:
        return

    active_admin_count = (
        db.query(User)
        .filter(
            User.role == "admin",
            User.is_active.is_(True),
        )
        .count()
    )

    if active_admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove or deactivate the last active administrator.",
        )


# -------------------------
# List users
# -------------------------

@router.get(
    "",
    response_model=list[AdminUserResponse],
)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return users


# -------------------------
# Update user role
# -------------------------

@router.patch(
    "/{user_id}/role",
    response_model=AdminUserResponse,
)
def update_user_role(
    user_id: UUID,
    payload: UpdateRoleRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        # All admin role/status changes acquire this lock first.
        lock_admin_accounts(db)

        target = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if target.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role.",
            )

        if target.role == "admin" and payload.role == "user":
            ensure_another_active_admin(db, target)

        target.role = payload.role
        db.commit()
        db.refresh(target)
        return target

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update user role.",
        )


# -------------------------
# Update user account status
# -------------------------

@router.patch(
    "/{user_id}/status",
    response_model=AdminUserResponse,
)
def update_user_status(
    user_id: UUID,
    payload: UpdateStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        lock_admin_accounts(db)

        target = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if target.id == admin.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )

        if target.role == "admin" and target.is_active and not payload.is_active:
            ensure_another_active_admin(db, target)

        target.is_active = payload.is_active
        db.commit()
        db.refresh(target)
        return target

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update user status.",
        )