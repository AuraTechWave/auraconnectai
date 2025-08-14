"""
Customer Router V2 - Using Standardized Response Format

Example implementation showing how to use the new standardized response format.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from core.database import get_db
from core.auth import get_current_user, User
from core.response_models import (
    StandardResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ValidationErrorResponse
)
from core.response_utils import (
    PaginationParams,
    create_response,
    create_paginated_response,
    create_error_response,
    response_wrapper
)
from ..models.customer_models import Customer
from ..schemas.customer_schemas import (
    Customer as CustomerSchema,
    CustomerCreate,
    CustomerUpdate,
    CustomerSearchParams,
    CustomerProfile
)
from ..services.customer_service import CustomerService
from ..services.order_history_service import OrderHistoryService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/customers", tags=["customers-v2"])


def check_permission(user: User, action: str):
    """Check if user has required permission"""
    if not user.has_permission(f"customer:{action}"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("", response_model=StandardResponse[List[CustomerSchema]])
async def list_customers(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tier: Optional[str] = Query(None, description="Filter by tier"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List customers with pagination and filtering
    
    Returns standardized response with pagination metadata
    """
    check_permission(current_user, "read")
    
    try:
        service = CustomerService(db)
        
        # Build query
        query = db.query(Customer)
        
        # Apply filters
        if search:
            query = query.filter(
                Customer.name.ilike(f"%{search}%") |
                Customer.email.ilike(f"%{search}%") |
                Customer.phone.ilike(f"%{search}%")
            )
        if status:
            query = query.filter(Customer.status == status)
        if tier:
            query = query.filter(Customer.tier == tier)
        
        # Apply tenant filtering
        query = query.filter(Customer.restaurant_id == current_user.restaurant_id)
        
        # Paginate
        customers, total = pagination.paginate_query(query)
        
        # Convert to schemas
        customer_schemas = [CustomerSchema.from_orm(c) for c in customers]
        
        # Return paginated response
        return create_paginated_response(
            items=customer_schemas,
            pagination_params=pagination,
            total=total,
            message="Customers retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error listing customers: {str(e)}")
        return create_error_response(
            message="Failed to retrieve customers",
            code="DATABASE_ERROR",
            status_code=500
        )


@router.get("/{customer_id}", response_model=StandardResponse[CustomerSchema])
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get customer by ID
    
    Returns standardized response with customer data
    """
    check_permission(current_user, "read")
    
    service = CustomerService(db)
    customer = service.get_customer(customer_id)
    
    if not customer:
        return NotFoundResponse.create("Customer", customer_id)
    
    # Check tenant access
    if customer.restaurant_id != current_user.restaurant_id:
        return ForbiddenResponse.create("Access to this customer is forbidden")
    
    return StandardResponse.success(
        data=CustomerSchema.from_orm(customer),
        message="Customer retrieved successfully"
    )


@router.post("", response_model=StandardResponse[CustomerSchema])
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new customer
    
    Returns standardized response with created customer
    """
    check_permission(current_user, "write")
    
    try:
        service = CustomerService(db)
        
        # Check for duplicate email
        existing = db.query(Customer).filter(
            Customer.email == customer_data.email,
            Customer.restaurant_id == current_user.restaurant_id
        ).first()
        
        if existing:
            return StandardResponse.error(
                message="Customer with this email already exists",
                code="DUPLICATE_EMAIL"
            )
        
        # Create customer
        customer = service.create_customer(
            customer_data,
            restaurant_id=current_user.restaurant_id
        )
        
        return StandardResponse.success(
            data=CustomerSchema.from_orm(customer),
            message="Customer created successfully"
        )
        
    except ValueError as e:
        return ValidationErrorResponse.from_validation_errors({"general": [str(e)]})
    except Exception as e:
        logger.error(f"Error creating customer: {str(e)}")
        return StandardResponse.error(
            message="Failed to create customer",
            code="DATABASE_ERROR"
        )


@router.put("/{customer_id}", response_model=StandardResponse[CustomerSchema])
async def update_customer(
    customer_id: int,
    update_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update customer information
    
    Returns standardized response with updated customer
    """
    check_permission(current_user, "write")
    
    try:
        service = CustomerService(db)
        
        # Get existing customer
        customer = service.get_customer(customer_id)
        if not customer:
            return NotFoundResponse.create("Customer", customer_id)
        
        # Check tenant access
        if customer.restaurant_id != current_user.restaurant_id:
            return ForbiddenResponse.create("Access to this customer is forbidden")
        
        # Update customer
        updated_customer = service.update_customer(customer_id, update_data)
        
        return StandardResponse.success(
            data=CustomerSchema.from_orm(updated_customer),
            message="Customer updated successfully"
        )
        
    except ValueError as e:
        return ValidationErrorResponse.from_validation_errors({"general": [str(e)]})
    except Exception as e:
        logger.error(f"Error updating customer: {str(e)}")
        return StandardResponse.error(
            message="Failed to update customer",
            code="DATABASE_ERROR"
        )


@router.delete("/{customer_id}", response_model=StandardResponse[None])
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a customer
    
    Returns standardized response confirming deletion
    """
    check_permission(current_user, "delete")
    
    try:
        service = CustomerService(db)
        
        # Get existing customer
        customer = service.get_customer(customer_id)
        if not customer:
            return NotFoundResponse.create("Customer", customer_id)
        
        # Check tenant access
        if customer.restaurant_id != current_user.restaurant_id:
            return ForbiddenResponse.create("Access to this customer is forbidden")
        
        # Delete customer
        service.delete_customer(customer_id)
        
        return StandardResponse.success(
            data=None,
            message="Customer deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting customer: {str(e)}")
        return StandardResponse.error(
            message="Failed to delete customer",
            code="DATABASE_ERROR"
        )


@router.get("/{customer_id}/profile", response_model=StandardResponse[CustomerProfile])
@response_wrapper
async def get_customer_profile(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get complete customer profile with related data
    
    Uses @response_wrapper decorator for automatic response standardization
    """
    check_permission(current_user, "read")
    
    service = CustomerService(db)
    order_service = OrderHistoryService(db)
    
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check tenant access
    if customer.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Access forbidden")
    
    # Get related data
    recent_orders = order_service.get_order_summaries(customer_id, limit=5)
    favorite_items = order_service.get_favorite_items(customer_id, limit=5)
    
    # Build profile
    profile = CustomerProfile(
        **customer.__dict__,
        recent_orders=recent_orders,
        favorite_items=favorite_items
    )
    
    # The @response_wrapper will automatically wrap this in StandardResponse
    return profile


@router.post("/bulk", response_model=StandardResponse[dict])
async def bulk_create_customers(
    customers: List[CustomerCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk create customers
    
    Returns standardized response with creation results
    """
    check_permission(current_user, "write")
    
    if len(customers) > 100:
        return StandardResponse.error(
            message="Cannot create more than 100 customers at once",
            code="BATCH_SIZE_EXCEEDED"
        )
    
    service = CustomerService(db)
    results = {
        "created": [],
        "failed": []
    }
    
    for customer_data in customers:
        try:
            # Check for duplicate
            existing = db.query(Customer).filter(
                Customer.email == customer_data.email,
                Customer.restaurant_id == current_user.restaurant_id
            ).first()
            
            if existing:
                results["failed"].append({
                    "email": customer_data.email,
                    "reason": "Duplicate email"
                })
                continue
            
            # Create customer
            customer = service.create_customer(
                customer_data,
                restaurant_id=current_user.restaurant_id
            )
            results["created"].append(CustomerSchema.from_orm(customer))
            
        except Exception as e:
            results["failed"].append({
                "email": customer_data.email,
                "reason": str(e)
            })
    
    return StandardResponse.success(
        data=results,
        message=f"Created {len(results['created'])} customers, {len(results['failed'])} failed"
    )