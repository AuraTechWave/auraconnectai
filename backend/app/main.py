from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from typing import Optional
from core.exceptions import register_exception_handlers
from app.startup import run_startup_checks
from modules.staff.routes.staff_routes import router as staff_router
from modules.staff.routes.payroll_routes import (
    router as payroll_router
)
from modules.staff.routes.enhanced_payroll_routes import (
    router as enhanced_payroll_router
)
from modules.staff.routers.biometric_router import router as biometric_router
from modules.staff.routers.scheduling_router import router as scheduling_router
from modules.auth.routes.auth_routes import (
    router as auth_router
)
# TODO: Fix RBAC routes - SQLAlchemy/Pydantic mismatch
# from modules.auth.routes.rbac_routes import (
#     router as rbac_router
# )
# TODO: Fix password routes - SQLAlchemy/Pydantic mismatch
# from modules.auth.routes.password_routes import (
#     router as password_router
# )
from modules.orders.routes.order_routes import router as order_router
from modules.orders.routes.inventory_routes import (
    router as inventory_router
)
from modules.orders.routes.inventory_impact_routes import (
    router as inventory_impact_router
)
from modules.orders.routes.kitchen_routes import (
    router as kitchen_router
)
from modules.orders.routes.print_ticket_routes import (
    router as print_ticket_router
)
from modules.orders.routes.pricing_routes import (
    router as pricing_router
)
from modules.orders.routers.sync import (
    sync_router as order_sync_router
)
from modules.orders.routers.pos_sync import (
    router as order_pos_sync_router
)
from modules.orders.routers.external_pos_webhook_router import (
    router as external_pos_webhook_router
)
from modules.orders.routers.webhook_monitoring_router import (
    router as webhook_monitoring_router
)
from modules.tax.routes.tax_routes import router as tax_router
from modules.payroll import payroll_router
from modules.settings.routes.pos_sync_routes import (
    router as pos_sync_router
)
from modules.pos.routes.pos_routes import router as pos_router
from modules.orders.routes.webhook_routes import (
    router as webhook_router
)
from modules.menu.routes.menu_routes import (
    router as menu_router
)
from modules.menu.routes.inventory_routes import (
    router as menu_inventory_router
)
from modules.menu.routes.versioning_routes import (
    router as menu_versioning_router
)
from modules.inventory.routes.inventory_routes import (
    router as inventory_management_router
)
from modules.inventory.routes.vendor_routes import (
    router as vendor_management_router
)
from modules.analytics.routers.analytics_router import (
    router as analytics_router
)
from modules.analytics.routers.realtime_router import (
    router as realtime_analytics_router  
)
from modules.analytics.routers.ai_insights_router import (
    router as ai_insights_router
)
from modules.analytics.routers.pos import (
    router as pos_analytics_router
)
from modules.ai_recommendations.routers import (
    router as ai_recommendations_router
)
from modules.customers.routers.customer_router import router as customer_router
from app.api.v1.endpoints.reservations import router as reservation_router
from modules.payments.api import payment_router
from core.menu_versioning_triggers import init_versioning_triggers
from modules.orders.tasks.sync_tasks import (
    start_sync_scheduler,
    stop_sync_scheduler
)
from modules.orders.tasks.webhook_retry_task import (
    start_webhook_retry_scheduler,
    stop_webhook_retry_scheduler
)

# FastAPI app with enhanced OpenAPI documentation
app = FastAPI(
    title="AuraConnect AI - Restaurant Management API",
    description="""
    Comprehensive restaurant management platform API with advanced payroll processing,
    tax calculations, and POS integration capabilities.
    
    ## Features
    
    * **Enhanced Payroll Processing** - Complete payroll engine with tax integration
    * **Tax Services** - Multi-jurisdiction tax calculations with real-time rates
    * **Staff Management** - Employee scheduling, attendance, and role management
    * **Order Management** - Complete order lifecycle management
    * **POS Integration** - Connect with major POS systems (Square, Toast, Clover)
    * **Menu Management** - Complete CRUD for menu items, categories, and modifiers
    * **Menu Versioning** - Complete version control and audit trail for menu changes
    * **Inventory Management** - Real-time inventory tracking with low-stock alerts
    * **Vendor Management** - Comprehensive vendor and purchase order management
    * **Analytics & Reporting** - Comprehensive business intelligence
    
    ## Authentication
    
    Most endpoints require JWT authentication. Use the `/auth/login` endpoint to obtain a token.
    
    ### Test Credentials:
    - **Admin**: username=`admin`, password=`secret`
    - **Payroll Manager**: username=`payroll_clerk`, password=`secret`  
    - **Manager**: username=`manager`, password=`secret`
    
    ## API Versioning
    
    This API follows semantic versioning. Current version includes:
    - Phase 3: Enhanced Payroll Engine
    - Phase 4: API & Schemas with Authentication
    
    """,
    version="4.0.0",
    contact={
        "name": "AuraConnect AI Support",
        "url": "https://auraconnect.ai/support",
        "email": "support@auraconnect.ai",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://auraconnect.ai/license",
    },
)

# Register exception handlers for consistent error responses
register_exception_handlers(app)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://app.auraconnect.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers with proper order (auth first)
app.include_router(auth_router)
# app.include_router(rbac_router)  # TODO: Fix RBAC routes
# app.include_router(password_router)  # TODO: Fix password routes
app.include_router(enhanced_payroll_router)  # Phase 4 enhanced payroll API
app.include_router(staff_router)
app.include_router(payroll_router)  # Legacy payroll routes
app.include_router(biometric_router, prefix="/api/v1/staff", tags=["Staff Biometrics"])
app.include_router(scheduling_router, prefix="/api/v1/staff", tags=["Staff Scheduling"])
app.include_router(order_router)
app.include_router(inventory_router)
app.include_router(inventory_impact_router)
app.include_router(kitchen_router)
app.include_router(print_ticket_router)
app.include_router(pricing_router)
app.include_router(order_sync_router)
app.include_router(order_pos_sync_router)
app.include_router(external_pos_webhook_router)
app.include_router(webhook_monitoring_router)
app.include_router(tax_router)
app.include_router(payroll_router)  # Phase 3 payroll module routes
app.include_router(pos_sync_router)
app.include_router(pos_router)
app.include_router(webhook_router)
app.include_router(menu_router)
app.include_router(menu_inventory_router)
app.include_router(menu_versioning_router)
app.include_router(inventory_management_router)
app.include_router(vendor_management_router)
app.include_router(analytics_router)
app.include_router(realtime_analytics_router)
app.include_router(ai_insights_router)
app.include_router(pos_analytics_router)
app.include_router(ai_recommendations_router)
app.include_router(customer_router)
app.include_router(reservation_router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(payment_router, prefix="/api/v1/payments", tags=["Payments"])

# Initialize menu versioning triggers
init_versioning_triggers()


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    # Run startup validation checks
    passed, warnings = run_startup_checks()
    
    # Start order sync scheduler
    await start_sync_scheduler()
    # Start webhook retry scheduler
    await start_webhook_retry_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    # Stop order sync scheduler
    await stop_sync_scheduler()
    # Stop webhook retry scheduler
    await stop_webhook_retry_scheduler()


@app.get("/")
def read_root():
    return {"message": "AuraConnect backend is running"}


@app.get("/test-token")
async def test_token(authorization: Optional[str] = Depends(HTTPBearer(auto_error=False))):
    """Test endpoint to debug token issues - DISABLED IN PRODUCTION"""
    import os
    
    # Disable in production
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="Not found")
    
    from core.auth import verify_token, SECRET_KEY
    
    if not authorization:
        return {"error": "No authorization header"}
    
    token = authorization.credentials
    
    # Try to decode without verification first
    try:
        from jose import jwt
        # Decode without verification to see the payload
        payload_unverified = jwt.get_unverified_claims(token)
        
        # Now try with verification
        try:
            payload_verified = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            token_data = verify_token(token)
            
            return {
                "status": "success",
                "payload_unverified": payload_unverified,
                "payload_verified": payload_verified,
                "token_data": token_data.__dict__ if token_data else None,
                "secret_key_preview": SECRET_KEY[:10] + "..."
            }
        except Exception as e:
            return {
                "status": "verification_failed",
                "payload_unverified": payload_unverified,
                "error": str(e),
                "secret_key_preview": SECRET_KEY[:10] + "..."
            }
    except Exception as e:
        return {
            "status": "decode_failed",
            "error": str(e)
        }
