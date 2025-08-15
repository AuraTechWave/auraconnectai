# backend/modules/customers/routers/customer_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from core.database import get_db
from core.auth import get_current_user
from core.auth import User
from ..models.customer_models import Customer
from ..schemas.customer_schemas import (
    Customer as CustomerSchema,
    CustomerCreate,
    CustomerUpdate,
    CustomerSearchParams,
    CustomerSearchResponse,
    CustomerProfile,
    CustomerAnalytics,
    CustomerStatusUpdate,
    CustomerTierUpdate,
    CustomerAddressCreate,
    CustomerAddressUpdate,
    CustomerAddress,
    CustomerPreferenceCreate,
    CustomerPreference,
    OrderSummary,
    MenuItemSummary,
)
from ..services.customer_service import CustomerService, CustomerAuthService
from ..services.order_history_service import OrderHistoryService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/customers", tags=["customers"])


# Helper function to check permissions
def check_customer_permission(
    user: User,
    action: str,
    tenant_id: Optional[int] = None,
    resource_id: Optional[int] = None,
):
    """Check if user has customer-related permissions with tenant and resource scope"""
    # Get user's active tenant if not specified
    if tenant_id is None:
        tenant_id = user.default_tenant_id

    # Check base permission
    permission_key = f"customer:{action}"
    if not user.has_permission(permission_key, tenant_id):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions for {permission_key} in tenant {tenant_id}",
        )

    # Additional checks for specific resources
    if resource_id and action in ["read", "write", "delete"]:
        # Check if user has access to specific customer resource
        # This could be expanded to check customer-specific permissions
        # For now, we rely on tenant-level permissions
        pass

    # Log permission check for audit
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Permission check: user={user.id}, action={permission_key}, tenant={tenant_id}, resource={resource_id}"
    )


@router.post("/", response_model=CustomerSchema)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new customer"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        customer = customer_service.create_customer(customer_data)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating customer: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}", response_model=CustomerSchema)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer by ID"""
    check_customer_permission(current_user, "read")

    customer_service = CustomerService(db)
    customer = customer_service.get_customer(customer_id)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.get("/{customer_id}/profile", response_model=CustomerProfile)
async def get_customer_profile(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get complete customer profile with related data"""
    check_customer_permission(current_user, "read")

    customer_service = CustomerService(db)
    order_history_service = OrderHistoryService(db)

    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get related data
    recent_orders = order_history_service.get_order_summaries(customer_id, limit=5)
    favorite_items = order_history_service.get_favorite_items(customer_id, limit=5)

    # Build profile response
    profile = CustomerProfile(
        **customer.__dict__, recent_orders=recent_orders, favorite_items=favorite_items
    )

    return profile


@router.put("/{customer_id}", response_model=CustomerSchema)
async def update_customer(
    customer_id: int,
    update_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update customer information"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        customer = customer_service.update_customer(customer_id, update_data)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{customer_id}/status", response_model=CustomerSchema)
async def update_customer_status(
    customer_id: int,
    status_update: CustomerStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update customer status"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        customer = customer_service.update_customer_status(customer_id, status_update)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating customer status {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{customer_id}/tier", response_model=CustomerSchema)
async def update_customer_tier(
    customer_id: int,
    tier_update: CustomerTierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update customer loyalty tier"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        customer = customer_service.update_customer_tier(customer_id, tier_update)
        return customer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating customer tier {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=CustomerSearchResponse)
async def search_customers(
    query: Optional[str] = Query(None, description="Search in name, email, phone"),
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    tier: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    min_orders: Optional[int] = Query(None, ge=0),
    max_orders: Optional[int] = Query(None, ge=0),
    min_spent: Optional[float] = Query(None, ge=0),
    max_spent: Optional[float] = Query(None, ge=0),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    last_order_after: Optional[datetime] = Query(None),
    last_order_before: Optional[datetime] = Query(None),
    has_active_rewards: Optional[bool] = Query(None),
    location_id: Optional[int] = Query(None),
    tags: Optional[List[str]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "created_at",
        pattern="^(created_at|updated_at|last_order_date|total_spent|total_orders)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search and filter customers"""
    check_customer_permission(current_user, "read")

    # Build search parameters
    search_params = CustomerSearchParams(
        query=query,
        email=email,
        phone=phone,
        tier=tier,
        status=status,
        min_orders=min_orders,
        max_orders=max_orders,
        min_spent=min_spent,
        max_spent=max_spent,
        created_after=created_after,
        created_before=created_before,
        last_order_after=last_order_after,
        last_order_before=last_order_before,
        has_active_rewards=has_active_rewards,
        location_id=location_id,
        tags=tags,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    try:
        customer_service = CustomerService(db)
        customers, total = customer_service.search_customers(search_params)

        total_pages = (total + page_size - 1) // page_size

        return CustomerSearchResponse(
            customers=customers,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Error searching customers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/analytics", response_model=CustomerAnalytics)
async def get_customer_analytics(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer analytics and insights"""
    check_customer_permission(current_user, "read")

    try:
        customer_service = CustomerService(db)
        analytics = customer_service.get_customer_analytics(customer_id)
        return analytics
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting customer analytics {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Address management endpoints
@router.post("/{customer_id}/addresses", response_model=CustomerAddress)
async def add_customer_address(
    customer_id: int,
    address_data: CustomerAddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new address for customer"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        address = customer_service.add_customer_address(customer_id, address_data)
        return address
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding address for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/addresses/{address_id}", response_model=CustomerAddress)
async def update_customer_address(
    address_id: int,
    update_data: CustomerAddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update customer address"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        address = customer_service.update_customer_address(address_id, update_data)
        return address
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating address {address_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/addresses/{address_id}")
async def delete_customer_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete customer address"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        success = customer_service.delete_customer_address(address_id)
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting address {address_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Preference management endpoints
@router.post("/{customer_id}/preferences", response_model=CustomerPreference)
async def set_customer_preference(
    customer_id: int,
    preference_data: CustomerPreferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or update customer preference"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        preference = customer_service.set_customer_preference(
            customer_id, preference_data
        )
        return preference
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting preference for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/preferences", response_model=List[CustomerPreference])
async def get_customer_preferences(
    customer_id: int,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer preferences"""
    check_customer_permission(current_user, "read")

    try:
        customer_service = CustomerService(db)
        preferences = customer_service.get_customer_preferences(customer_id, category)
        return preferences
    except Exception as e:
        logger.error(f"Error getting preferences for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Loyalty and rewards endpoints
@router.post("/{customer_id}/loyalty/add-points")
async def add_loyalty_points(
    customer_id: int,
    points: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add loyalty points to customer"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        customer = customer_service.add_loyalty_points(customer_id, points, reason)
        return {"success": True, "new_balance": customer.loyalty_points}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error adding loyalty points for customer {customer_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{customer_id}/loyalty/redeem-points")
async def redeem_loyalty_points(
    customer_id: int,
    points: int,
    reward_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Redeem loyalty points"""
    check_customer_permission(current_user, "write")

    try:
        customer_service = CustomerService(db)
        success = customer_service.redeem_loyalty_points(customer_id, points, reward_id)
        return {"success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error redeeming loyalty points for customer {customer_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# Order history endpoints
@router.get("/{customer_id}/orders", response_model=List[OrderSummary])
async def get_customer_orders(
    customer_id: int,
    status_filter: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer's order history"""
    check_customer_permission(current_user, "read")

    try:
        order_history_service = OrderHistoryService(db)
        orders, total = order_history_service.get_customer_orders(
            customer_id, status_filter, date_from, date_to, limit, offset
        )

        # Convert to order summaries
        summaries = []
        for order in orders:
            total_amount = sum(item.price * item.quantity for item in order.order_items)
            item_count = sum(item.quantity for item in order.order_items)

            summary = OrderSummary(
                id=order.id,
                order_number=f"ORD-{order.id:06d}",
                status=order.status,
                total_amount=float(total_amount),
                item_count=item_count,
                created_at=order.created_at,
                fulfilled_at=order.updated_at if order.status == "completed" else None,
            )
            summaries.append(summary)

        return summaries
    except Exception as e:
        logger.error(f"Error getting orders for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/favorite-items", response_model=List[MenuItemSummary])
async def get_customer_favorite_items(
    customer_id: int,
    limit: int = Query(10, ge=1, le=50),
    min_orders: int = Query(2, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get customer's favorite menu items"""
    check_customer_permission(current_user, "read")

    try:
        order_history_service = OrderHistoryService(db)
        favorites = order_history_service.get_favorite_items(
            customer_id, limit, min_orders
        )
        return favorites
    except Exception as e:
        logger.error(
            f"Error getting favorite items for customer {customer_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# Customer authentication endpoints (separate from staff auth)
@router.post("/auth/register")
async def register_customer(
    customer_data: CustomerCreate, db: Session = Depends(get_db)
):
    """Register a new customer account"""
    try:
        from ..auth.customer_auth import CustomerAuthService

        auth_service = CustomerAuthService(db)
        customer = auth_service.register_customer(customer_data)

        # Create access token
        token_response = auth_service.create_access_token(customer)

        return {"message": "Registration successful", **token_response}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering customer: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/login")
async def authenticate_customer(
    email: str, password: str, db: Session = Depends(get_db)
):
    """Authenticate customer login"""
    try:
        from ..auth.customer_auth import CustomerAuthService

        auth_service = CustomerAuthService(db)
        customer = auth_service.authenticate_customer(email, password)

        if not customer:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Generate JWT token
        token_response = auth_service.create_access_token(customer)

        return {"message": "Login successful", **token_response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authenticating customer: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/refresh")
async def refresh_customer_token(db: Session = Depends(get_db)):
    """Refresh customer access token"""
    try:
        from ..auth.customer_auth import get_current_customer, CustomerAuthService

        current_customer = await get_current_customer(db=db)
        auth_service = CustomerAuthService(db)

        token_response = auth_service.refresh_token(current_customer)

        return {"message": "Token refreshed successfully", **token_response}
    except Exception as e:
        logger.error(f"Error refreshing customer token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/logout")
async def logout_customer(db: Session = Depends(get_db)):
    """Logout customer (revoke token)"""
    try:
        from ..auth.customer_auth import get_current_customer, CustomerAuthService

        current_customer = await get_current_customer(db=db)
        auth_service = CustomerAuthService(db)

        auth_service.revoke_token(current_customer.id)

        return {"message": "Logout successful"}
    except Exception as e:
        logger.error(f"Error logging out customer: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/change-password")
async def change_customer_password(
    old_password: str, new_password: str, db: Session = Depends(get_db)
):
    """Change customer password"""
    try:
        from ..auth.customer_auth import get_current_customer, CustomerAuthService

        current_customer = await get_current_customer(db=db)
        auth_service = CustomerAuthService(db)

        success = auth_service.change_password(
            current_customer.id, old_password, new_password
        )

        return {"message": "Password changed successfully", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error changing customer password: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/reset-password-request")
async def request_password_reset(email: str, db: Session = Depends(get_db)):
    """Request password reset"""
    try:
        from ..auth.customer_auth import CustomerAuthService

        auth_service = CustomerAuthService(db)
        reset_token = auth_service.reset_password_request(email)

        # In production, send email with reset link
        # For now, return success regardless of email existence for security
        return {"message": "If the email exists, a reset link has been sent"}
    except Exception as e:
        logger.error(f"Error requesting password reset: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/reset-password")
async def reset_customer_password(
    reset_token: str, new_password: str, db: Session = Depends(get_db)
):
    """Reset customer password using reset token"""
    try:
        from ..auth.customer_auth import CustomerAuthService

        auth_service = CustomerAuthService(db)
        success = auth_service.reset_password(reset_token, new_password)

        return {"message": "Password reset successful", "success": success}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error resetting customer password: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
