from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.modules.staff.routes.staff_routes import router as staff_router
from backend.modules.staff.routes.payroll_routes import (
    router as payroll_router
)
from backend.modules.staff.routes.enhanced_payroll_routes import (
    router as enhanced_payroll_router
)
from backend.modules.auth.routes.auth_routes import (
    router as auth_router
)
from backend.modules.orders.routes.order_routes import router as order_router
from backend.modules.orders.routes.inventory_routes import (
    router as inventory_router
)
from backend.modules.orders.routes.kitchen_routes import (
    router as kitchen_router
)
from backend.modules.orders.routes.print_ticket_routes import (
    router as print_ticket_router
)
from backend.modules.orders.routes.pricing_routes import (
    router as pricing_router
)
from backend.modules.tax.routes.tax_routes import router as tax_router
from backend.modules.settings.routes.pos_sync_routes import (
    router as pos_sync_router
)
from backend.modules.pos.routes.pos_routes import router as pos_router
from backend.modules.orders.routes.webhook_routes import (
    router as webhook_router
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
    * **Inventory Management** - Real-time inventory tracking and updates
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

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.auraconnect.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers with proper order (auth first)
app.include_router(auth_router)
app.include_router(enhanced_payroll_router)  # Phase 4 enhanced payroll API
app.include_router(staff_router)
app.include_router(payroll_router)  # Legacy payroll routes
app.include_router(order_router)
app.include_router(inventory_router)
app.include_router(kitchen_router)
app.include_router(print_ticket_router)
app.include_router(pricing_router)
app.include_router(tax_router)
app.include_router(pos_sync_router)
app.include_router(pos_router)
app.include_router(webhook_router)


@app.get("/")
def read_root():
    return {"message": "AuraConnect backend is running"}
