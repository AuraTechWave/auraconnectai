"""
Permission utilities for staff scheduling
"""

from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.staff_models import StaffMember, Role


class SchedulingPermissions:
    """Permission checks for scheduling operations"""

    # Define role-based permissions
    PERMISSIONS = {
        "admin": [
            "create_template",
            "update_template",
            "delete_template",
            "create_shift",
            "update_shift",
            "delete_shift",
            "approve_swap",
            "reject_swap",
            "publish_schedule",
            "generate_schedule",
            "view_analytics",
            "manage_all_staff",
        ],
        "manager": [
            "create_template",
            "update_template",
            "create_shift",
            "update_shift",
            "delete_shift",
            "approve_swap",
            "reject_swap",
            "publish_schedule",
            "generate_schedule",
            "view_analytics",
            "manage_location_staff",
        ],
        "supervisor": [
            "create_shift",
            "update_shift",
            "approve_swap",
            "view_analytics",
            "manage_team_staff",
        ],
        "staff": [
            "view_own_schedule",
            "request_swap",
            "update_availability",
            "view_own_analytics",
        ],
    }

    @staticmethod
    def check_permission(
        user_id: int,
        permission: str,
        db: Session,
        location_id: Optional[int] = None,
        staff_id: Optional[int] = None,
    ) -> bool:
        """Check if a user has a specific permission"""
        # Get user's staff record
        staff = db.query(StaffMember).filter(StaffMember.user_id == user_id).first()

        if not staff:
            return False

        # Get user's role
        role = staff.role
        if not role:
            return False

        role_name = role.name.lower()

        # Check if role has permission
        if role_name in SchedulingPermissions.PERMISSIONS:
            role_permissions = SchedulingPermissions.PERMISSIONS[role_name]

            # Special handling for location-based permissions
            if permission == "manage_location_staff" and location_id:
                # Check if user manages this location
                return staff.managed_location_id == location_id

            # Special handling for self-permissions
            if permission in ["view_own_schedule", "view_own_analytics"]:
                return staff_id == staff.id or permission in role_permissions

            return permission in role_permissions

        return False

    @staticmethod
    def require_permission(
        user_id: int,
        permission: str,
        db: Session,
        location_id: Optional[int] = None,
        staff_id: Optional[int] = None,
    ):
        """Require a permission or raise an exception"""
        if not SchedulingPermissions.check_permission(
            user_id, permission, db, location_id, staff_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission} required",
            )

    @staticmethod
    def get_user_role(user_id: int, db: Session) -> Optional[str]:
        """Get user's role name"""
        staff = db.query(StaffMember).filter(StaffMember.user_id == user_id).first()

        if staff and staff.role:
            return staff.role.name.lower()

        return None

    @staticmethod
    def can_manage_staff(user_id: int, target_staff_id: int, db: Session) -> bool:
        """Check if user can manage a specific staff member"""
        user_role = SchedulingPermissions.get_user_role(user_id, db)

        if user_role == "admin":
            return True

        # Get user's staff record
        user_staff = (
            db.query(StaffMember).filter(StaffMember.user_id == user_id).first()
        )

        # Get target staff record
        target_staff = (
            db.query(StaffMember).filter(StaffMember.id == target_staff_id).first()
        )

        if not user_staff or not target_staff:
            return False

        # Manager can manage staff in their location
        if user_role == "manager":
            return user_staff.location_id == target_staff.location_id

        # Supervisor can manage staff in their team
        if user_role == "supervisor":
            return user_staff.team_id == target_staff.team_id

        # Staff can only manage themselves
        return user_staff.id == target_staff_id
