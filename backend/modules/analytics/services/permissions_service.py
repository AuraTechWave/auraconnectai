# backend/modules/analytics/services/permissions_service.py

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class AnalyticsPermission(str, Enum):
    """Analytics permissions hierarchy"""
    
    # View permissions
    VIEW_DASHBOARD = "analytics:view_dashboard"
    VIEW_SALES_REPORTS = "analytics:view_sales_reports"
    VIEW_STAFF_REPORTS = "analytics:view_staff_performance"
    VIEW_PRODUCT_REPORTS = "analytics:view_product_performance"
    
    # Export permissions
    EXPORT_REPORTS = "analytics:export_reports"
    EXPORT_SENSITIVE = "analytics:export_sensitive_data"
    
    # Alert permissions
    CREATE_ALERTS = "analytics:create_alerts"
    MANAGE_ALERTS = "analytics:manage_alerts"
    VIEW_ALL_ALERTS = "analytics:view_all_alerts"
    
    # Advanced permissions
    ACCESS_REALTIME = "analytics:access_realtime"
    MANAGE_SNAPSHOTS = "analytics:manage_snapshots"
    VIEW_ALL_STAFF = "analytics:view_all_staff_data"
    VIEW_FINANCIAL = "analytics:view_financial_details"
    
    # Admin permissions
    ADMIN_ANALYTICS = "analytics:admin"
    MANAGE_MATERIALIZED_VIEWS = "analytics:manage_views"
    SYSTEM_METRICS = "analytics:system_metrics"


class AnalyticsRole(str, Enum):
    """Predefined analytics roles with permission sets"""
    
    VIEWER = "analytics_viewer"
    ANALYST = "analytics_analyst" 
    MANAGER = "analytics_manager"
    ADMIN = "analytics_admin"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    AnalyticsRole.VIEWER: [
        AnalyticsPermission.VIEW_DASHBOARD,
        AnalyticsPermission.VIEW_SALES_REPORTS,
    ],
    
    AnalyticsRole.ANALYST: [
        AnalyticsPermission.VIEW_DASHBOARD,
        AnalyticsPermission.VIEW_SALES_REPORTS,
        AnalyticsPermission.VIEW_STAFF_REPORTS,
        AnalyticsPermission.VIEW_PRODUCT_REPORTS,
        AnalyticsPermission.EXPORT_REPORTS,
        AnalyticsPermission.ACCESS_REALTIME,
    ],
    
    AnalyticsRole.MANAGER: [
        AnalyticsPermission.VIEW_DASHBOARD,
        AnalyticsPermission.VIEW_SALES_REPORTS,
        AnalyticsPermission.VIEW_STAFF_REPORTS,
        AnalyticsPermission.VIEW_PRODUCT_REPORTS,
        AnalyticsPermission.EXPORT_REPORTS,
        AnalyticsPermission.EXPORT_SENSITIVE,
        AnalyticsPermission.ACCESS_REALTIME,
        AnalyticsPermission.CREATE_ALERTS,
        AnalyticsPermission.MANAGE_ALERTS,
        AnalyticsPermission.VIEW_ALL_STAFF,
        AnalyticsPermission.VIEW_FINANCIAL,
    ],
    
    AnalyticsRole.ADMIN: [
        # All permissions
        AnalyticsPermission.VIEW_DASHBOARD,
        AnalyticsPermission.VIEW_SALES_REPORTS,
        AnalyticsPermission.VIEW_STAFF_REPORTS,
        AnalyticsPermission.VIEW_PRODUCT_REPORTS,
        AnalyticsPermission.EXPORT_REPORTS,
        AnalyticsPermission.EXPORT_SENSITIVE,
        AnalyticsPermission.ACCESS_REALTIME,
        AnalyticsPermission.CREATE_ALERTS,
        AnalyticsPermission.MANAGE_ALERTS,
        AnalyticsPermission.VIEW_ALL_ALERTS,
        AnalyticsPermission.VIEW_ALL_STAFF,
        AnalyticsPermission.VIEW_FINANCIAL,
        AnalyticsPermission.ADMIN_ANALYTICS,
        AnalyticsPermission.MANAGE_SNAPSHOTS,
        AnalyticsPermission.MANAGE_MATERIALIZED_VIEWS,
        AnalyticsPermission.SYSTEM_METRICS,
    ]
}


class PermissionsService:
    """Service for managing analytics permissions and access control"""
    
    @staticmethod
    def get_user_permissions(user: Dict[str, Any]) -> List[AnalyticsPermission]:
        """Get all analytics permissions for a user"""
        
        permissions = set()
        
        # Get permissions from analytics role
        analytics_role = user.get("analytics_role")
        if analytics_role and analytics_role in ROLE_PERMISSIONS:
            permissions.update(ROLE_PERMISSIONS[analytics_role])
        
        # Get permissions from general role (fallback)
        general_role = user.get("role", "").lower()
        if general_role in ["manager", "admin", "owner"]:
            permissions.update(ROLE_PERMISSIONS[AnalyticsRole.MANAGER])
        elif general_role == "supervisor":
            permissions.update(ROLE_PERMISSIONS[AnalyticsRole.ANALYST])
        elif general_role in ["staff", "employee"]:
            permissions.update(ROLE_PERMISSIONS[AnalyticsRole.VIEWER])
        
        # Admin users get all permissions
        if user.get("is_admin") or general_role == "admin":
            permissions.update(ROLE_PERMISSIONS[AnalyticsRole.ADMIN])
        
        # Custom permissions from user object
        custom_permissions = user.get("analytics_permissions", [])
        if custom_permissions:
            permissions.update(custom_permissions)
        
        return list(permissions)
    
    @staticmethod
    def has_permission(user: Dict[str, Any], permission: AnalyticsPermission) -> bool:
        """Check if user has a specific permission"""
        
        user_permissions = PermissionsService.get_user_permissions(user)
        return permission in user_permissions
    
    @staticmethod
    def require_permission(user: Dict[str, Any], permission: AnalyticsPermission):
        """Require a specific permission, raise exception if not granted"""
        
        if not PermissionsService.has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Analytics permission required: {permission.value}"
            )
    
    @staticmethod
    def filter_data_by_permissions(
        user: Dict[str, Any], 
        data: Dict[str, Any],
        data_type: str
    ) -> Dict[str, Any]:
        """Filter sensitive data based on user permissions"""
        
        filtered_data = data.copy()
        user_permissions = PermissionsService.get_user_permissions(user)
        
        # Remove financial details if not permitted
        if AnalyticsPermission.VIEW_FINANCIAL not in user_permissions:
            sensitive_fields = [
                "total_revenue", "net_revenue", "gross_revenue", 
                "total_discounts", "revenue_generated", "cost_data"
            ]
            for field in sensitive_fields:
                if field in filtered_data:
                    filtered_data[field] = "[RESTRICTED]"
                    
        # Remove staff details if not permitted
        if AnalyticsPermission.VIEW_ALL_STAFF not in user_permissions:
            # Only show current user's data
            user_id = user.get("id")
            if data_type == "staff_performance" and filtered_data.get("staff_id") != user_id:
                filtered_data = {"error": "Access denied to other staff data"}
        
        return filtered_data
    
    @staticmethod
    def get_data_access_filters(user: Dict[str, Any]) -> Dict[str, Any]:
        """Get data access filters based on user permissions"""
        
        filters = {}
        user_permissions = PermissionsService.get_user_permissions(user)
        
        # Restrict to own data if limited permissions
        if AnalyticsPermission.VIEW_ALL_STAFF not in user_permissions:
            filters["staff_ids"] = [user.get("id")]
        
        # Time-based restrictions for viewers
        if AnalyticsPermission.VIEW_FINANCIAL not in user_permissions:
            # Limit to last 30 days for basic users
            from datetime import date, timedelta
            filters["max_date_range"] = 30
            
        return filters
    
    @staticmethod
    def can_export_format(user: Dict[str, Any], format_type: str) -> bool:
        """Check if user can export in specific format"""
        
        user_permissions = PermissionsService.get_user_permissions(user)
        
        # Basic export permission required
        if AnalyticsPermission.EXPORT_REPORTS not in user_permissions:
            return False
            
        # PDF/Excel exports may contain sensitive data
        if format_type.lower() in ["pdf", "xlsx"]:
            return AnalyticsPermission.EXPORT_SENSITIVE in user_permissions
            
        return True
    
    @staticmethod
    def get_accessible_metrics(user: Dict[str, Any]) -> List[str]:
        """Get list of metrics user can access"""
        
        user_permissions = PermissionsService.get_user_permissions(user)
        accessible_metrics = []
        
        # Basic metrics for all users
        if AnalyticsPermission.VIEW_SALES_REPORTS in user_permissions:
            accessible_metrics.extend(["orders", "customers", "items_sold"])
        
        # Financial metrics
        if AnalyticsPermission.VIEW_FINANCIAL in user_permissions:
            accessible_metrics.extend([
                "revenue", "discounts", "net_revenue", "average_order_value"
            ])
        
        # Staff metrics
        if AnalyticsPermission.VIEW_STAFF_REPORTS in user_permissions:
            accessible_metrics.extend([
                "staff_performance", "processing_time", "orders_per_hour"
            ])
        
        # Real-time metrics
        if AnalyticsPermission.ACCESS_REALTIME in user_permissions:
            accessible_metrics.extend([
                "realtime_revenue", "realtime_orders", "live_customers"
            ])
        
        return accessible_metrics


# Dependency functions for FastAPI
def require_analytics_permission(permission: AnalyticsPermission):
    """FastAPI dependency factory for permission checking"""
    
    def permission_dependency(current_user: Dict[str, Any]):
        PermissionsService.require_permission(current_user, permission)
        return current_user
    
    return permission_dependency


def require_analytics_role(role: AnalyticsRole):
    """FastAPI dependency factory for role checking"""
    
    def role_dependency(current_user: Dict[str, Any]):
        user_role = current_user.get("analytics_role")
        if user_role != role:
            # Check if user has higher role
            role_hierarchy = [
                AnalyticsRole.VIEWER,
                AnalyticsRole.ANALYST, 
                AnalyticsRole.MANAGER,
                AnalyticsRole.ADMIN
            ]
            
            current_level = role_hierarchy.index(user_role) if user_role in role_hierarchy else -1
            required_level = role_hierarchy.index(role) if role in role_hierarchy else 999
            
            if current_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Analytics role required: {role.value}"
                )
        
        return current_user
    
    return role_dependency


# Utility functions
def get_permission_summary(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get a summary of user's analytics permissions"""
    
    permissions = PermissionsService.get_user_permissions(user)
    accessible_metrics = PermissionsService.get_accessible_metrics(user)
    
    return {
        "user_id": user.get("id"),
        "analytics_role": user.get("analytics_role"),
        "permissions": [p.value for p in permissions],
        "accessible_metrics": accessible_metrics,
        "can_export": {
            "csv": PermissionsService.can_export_format(user, "csv"),
            "pdf": PermissionsService.can_export_format(user, "pdf"),
            "xlsx": PermissionsService.can_export_format(user, "xlsx")
        },
        "data_restrictions": PermissionsService.get_data_access_filters(user)
    }


def assign_analytics_role(user_id: int, role: AnalyticsRole) -> Dict[str, Any]:
    """Assign analytics role to a user (would integrate with user management)"""
    
    # This would update the user's analytics_role in the database
    logger.info(f"Assigned analytics role {role.value} to user {user_id}")
    
    return {
        "success": True,
        "user_id": user_id,
        "new_role": role.value,
        "permissions": [p.value for p in ROLE_PERMISSIONS[role]],
        "message": f"Analytics role {role.value} assigned successfully"
    }