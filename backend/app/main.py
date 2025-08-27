from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from typing import Optional
from core.exceptions import register_exception_handlers
from core.tenant_context import TenantIsolationMiddleware
from core.rate_limiter import RateLimitMiddleware
from core.response_middleware import ResponseStandardizationMiddleware, ErrorHandlingMiddleware
from app.startup import run_startup_checks

# ========== Authentication & Authorization ==========
from modules.auth.routes.auth_routes import router as auth_router
from modules.auth.routes.rbac_routes import router as rbac_router
from modules.auth.routes.password_routes import router as password_router

# ========== Staff Management ==========
from modules.staff.routes.staff_routes import router as staff_router
from modules.staff.routes.payroll_routes import router as payroll_router
from modules.staff.routes.enhanced_payroll_routes import router as enhanced_payroll_router
from modules.staff.routes.attendance_routes import router as attendance_router
from modules.staff.routes.shift_routes import router as shift_router
from modules.staff.routers.biometric_router import router as biometric_router
from modules.staff.routers.scheduling_router import router as scheduling_router
from modules.staff.routers.shift_swap_router import router as shift_swap_router
from modules.staff.routers.schedule_router import router as schedule_router

# ========== Orders Management ==========
from modules.orders.routes.order_routes import router as order_router
from modules.orders.routes.inventory_routes import router as inventory_router
from modules.orders.routes.inventory_impact_routes import router as inventory_impact_router
from modules.orders.routes.kitchen_routes import router as kitchen_router
from modules.orders.routes.print_ticket_routes import router as print_ticket_router
from modules.orders.routes.order_split_routes import router as order_split_router
from modules.orders.routes.routing_rules_routes import router as routing_rules_router
from modules.orders.routes.queue_routes import router as queue_router
from modules.orders.routes.queue_analytics_routes import router as queue_analytics_router
from modules.orders.routes.priority_routes import router as priority_router

# ========== Kitchen Display System (KDS) ==========
from modules.kds.routes.kds_routes import router as kds_router
from modules.orders.routes.pricing_routes import router as pricing_router
from modules.orders.routes.pricing_rule_routes import router as pricing_rule_router
from modules.orders.routes.payment_reconciliation_routes import router as payment_reconciliation_router
from modules.orders.routes.order_promotion_routes import router as order_promotion_router
# TODO: Fix missing schemas
# from modules.orders.routes.order_inventory_routes import router as order_inventory_router
from modules.orders.api.customer_tracking_endpoints import router as customer_tracking_router
from modules.orders.api.manual_review_endpoints import router as manual_review_router
from modules.orders.routers.sync import sync_router as order_sync_router
from modules.orders.routers.pos_sync import router as order_pos_sync_router
from modules.orders.routers.external_pos_webhook_router import router as external_pos_webhook_router
from modules.orders.routers.webhook_monitoring_router import router as webhook_monitoring_router
from modules.orders.routes.webhook_routes import router as webhook_router

# ========== Tax Management ==========
from modules.tax.routes.tax_routes import router as tax_router
from modules.tax.routes.tax_calculation_routes import router as tax_calculation_router
from modules.tax.routes.tax_compliance_routes import router as tax_compliance_router
from modules.tax.routes.tax_jurisdiction_routes import router as tax_jurisdiction_router

# ========== Payroll Management ==========
from modules.payroll import payroll_router
from modules.payroll.routes.configuration_routes import router as payroll_config_router
from modules.payroll.routes.overtime_rules_routes import router as overtime_rules_router
from modules.payroll.routes.pay_policy_routes import router as pay_policy_router
from modules.payroll.routes.payment_export_routes import router as payment_export_router
from modules.payroll.routes.payment_history_routes import router as payment_history_router
from modules.payroll.routes.payment_routes import router as payment_routes_router
from modules.payroll.routes.payment_summary_routes import router as payment_summary_router
from modules.payroll.routes.role_pay_rates_routes import router as role_pay_rates_router
from modules.payroll.routes.tax_calculation_routes import router as payroll_tax_calc_router

# ========== Settings & Configuration ==========
from modules.settings.routes.pos_sync_routes import router as pos_sync_router
from modules.settings.routes.settings_routes import router as settings_router
from modules.settings.routes.settings_ui_routes import router as settings_ui_router

# ========== POS Integration ==========
from modules.pos.routes.pos_routes import router as pos_router
from modules.pos_migration.routers.migration_router import router as pos_migration_router

# ========== Menu Management ==========
from modules.menu.routes.menu_routes import router as menu_router
from modules.menu.routes.inventory_routes import router as menu_inventory_router
from modules.menu.routes.versioning_routes import router as menu_versioning_router
from modules.menu.routes.recipe_routes import router as recipe_router
from modules.menu.routes.recipe_routes_optimized import router as recipe_router_optimized
from modules.menu.routes.recommendation_routes import router as menu_recommendation_router

# ========== Inventory Management ==========
from modules.inventory.routes.inventory_routes import router as inventory_management_router
from modules.inventory.routes.vendor_routes import router as vendor_management_router

# ========== Equipment Management ==========
from modules.equipment.routes import router as equipment_router

# ========== Analytics & Insights ==========
from modules.analytics.routers.analytics_router import router as analytics_router
from modules.analytics.routers.realtime_router import router as realtime_analytics_router
from modules.analytics.routers.ai_insights_router import router as ai_insights_router
from modules.analytics.routers.ai_chat_router import router as ai_chat_router
from modules.analytics.routers.predictive_analytics_router import router as predictive_analytics_router
from modules.analytics.routers.pos import router as pos_analytics_router

# ========== AI Recommendations ==========
from modules.ai_recommendations.routers import router as ai_recommendations_router
from modules.ai_recommendations.routers.admin_insights_router import router as admin_insights_router
from modules.ai_recommendations.routers.pricing_router import router as ai_pricing_router
from modules.ai_recommendations.routers.staffing_router import router as ai_staffing_router

# ========== Customer Management ==========
from modules.customers.routers.customer_router import router as customer_router
from modules.customers.routers.segment_router import router as customer_segment_router
# Old reservation router - replaced by enhanced reservation system
# from app.api.v1.endpoints.reservations import router as reservation_router

# ========== Reservations & Waitlist ==========
from modules.reservations import router as enhanced_reservation_router

# ========== Payments ==========
from modules.payments.api import payment_router

# ========== Feedback & Reviews ==========
from modules.feedback.routers.feedback_router import router as feedback_router
from modules.feedback.routers.reviews_router import router as reviews_router

# ========== Loyalty & Rewards ==========
from modules.loyalty.routers.rewards_router import router as rewards_router

# ========== Table Management ==========
from modules.tables.routers.table_layout_router import router as table_layout_router
from modules.tables.routers.table_state_router import router as table_state_router
from modules.tables.routes.analytics_routes import router as table_analytics_router
from modules.tables.routes.websocket_routes import router as table_websocket_router

# ========== Promotions & Marketing ==========
from modules.promotions.routers.promotion_router import router as promotion_router
from modules.promotions.routers.ab_testing_router import router as ab_testing_router
from modules.promotions.routers.analytics_router import router as promotion_analytics_router
from modules.promotions.routers.automation_router import router as automation_router
from modules.promotions.routers.coupon_router import router as coupon_router
from modules.promotions.routers.referral_router import router as referral_router
from modules.promotions.routers.scheduling_router import router as promotion_scheduling_router

# ========== Core Services & Tasks ==========
from core.menu_versioning_triggers import init_versioning_triggers
from modules.orders.tasks.sync_tasks import start_sync_scheduler, stop_sync_scheduler
from modules.orders.tasks.webhook_retry_task import start_webhook_retry_scheduler, stop_webhook_retry_scheduler
from modules.orders.tasks.pricing_rule_tasks import start_pricing_rule_worker, stop_pricing_rule_worker
from modules.orders.tasks.queue_tasks import start_queue_monitor, stop_queue_monitor
from modules.orders.tasks.priority_tasks import start_priority_monitor, stop_priority_monitor

# ========== GDPR Compliance ==========
from modules.gdpr.routes.gdpr_routes import router as gdpr_router

# ========== Health Monitoring ==========
from modules.health.routes.health_routes import router as health_router
from modules.health.metrics.performance_middleware import PerformanceMiddleware

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
    * **POS Migration** - AI-powered migration suite for seamless POS transitions
    * **Menu Management** - Complete CRUD for menu items, categories, and modifiers
    * **Menu Versioning** - Complete version control and audit trail for menu changes
    * **Recipe Management** - Bill of Materials (BOM) tracking with cost calculations
    * **Inventory Management** - Real-time inventory tracking with low-stock alerts
    * **Vendor Management** - Comprehensive vendor and purchase order management
    * **Analytics & Reporting** - Comprehensive business intelligence with AI insights
    * **Customer Management** - Customer profiles, order history, and preferences
    * **Feedback & Reviews** - Customer feedback collection and review management
    * **Kitchen Display System** - Real-time order routing and kitchen station management
    * **Loyalty & Rewards** - Points-based loyalty programs and rewards
    * **Table Management** - Restaurant floor layout and table state management
    * **Reservation System** - Advanced booking system with waitlist management and confirmations
    * **Promotions & Marketing** - Promotional campaigns, coupons, and A/B testing
    * **Payment Processing** - Multiple payment methods, split bills, and refunds
    * **Email Notifications** - Transactional emails with tracking, templates, and unsubscribe
    
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
    - Phase 5: Complete Feature Integration
    
    """,
    version="5.0.0",
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

# CRITICAL: Middleware order matters! They are executed in reverse order of addition

# 1. CORS middleware (needs to be last added/first executed for preflight requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://app.auraconnect.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Response standardization middleware
# Wraps all responses in standard format
app.add_middleware(
    ResponseStandardizationMiddleware,
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/health", "/metrics"]
)

# 3. Error handling middleware
# Catches and standardizes error responses
app.add_middleware(ErrorHandlingMiddleware)

# 4. Tenant isolation middleware
# Ensures tenant context is established for all requests
app.add_middleware(TenantIsolationMiddleware)

# 5. Rate limiting middleware (first to execute)
# Protects against DDoS and abuse before other processing
app.add_middleware(RateLimitMiddleware)

# 6. Performance monitoring middleware
# Tracks request performance and errors
app.add_middleware(PerformanceMiddleware)

# 7. Security middleware (must be after other middleware)
# Applies security headers, audit logging, and API version checks
from core.security_middleware import SecurityMiddleware
app.add_middleware(SecurityMiddleware)

# ========== Include all routers with proper order (auth first) ==========

# Authentication & Authorization
app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(password_router)

# Staff Management
app.include_router(enhanced_payroll_router)  # Phase 4 enhanced payroll API
app.include_router(staff_router)
app.include_router(payroll_router)  # Legacy payroll routes
app.include_router(attendance_router, prefix="/api/v1/staff", tags=["Staff Attendance"])
app.include_router(shift_router, prefix="/api/v1/staff", tags=["Staff Shifts"])
app.include_router(biometric_router, prefix="/api/v1/staff", tags=["Staff Biometrics"])
app.include_router(scheduling_router, prefix="/api/v1/staff", tags=["Staff Scheduling"])
app.include_router(shift_swap_router, prefix="/api/v1/staff", tags=["Shift Swapping"])
app.include_router(schedule_router, prefix="/api/v1/staff", tags=["Staff Schedule Management"])

# Orders Management
app.include_router(order_router)
app.include_router(inventory_router)
app.include_router(inventory_impact_router)
app.include_router(kitchen_router)
app.include_router(print_ticket_router)
app.include_router(order_split_router)
app.include_router(routing_rules_router)
app.include_router(queue_router)
app.include_router(queue_analytics_router)
app.include_router(priority_router)

# Kitchen Display System
app.include_router(kds_router)
app.include_router(pricing_router)
app.include_router(pricing_rule_router, prefix="/api/v1/orders", tags=["Pricing Rules"])
app.include_router(payment_reconciliation_router, prefix="/api/v1/orders", tags=["Payment Reconciliation"])
app.include_router(order_promotion_router, prefix="/api/v1/orders", tags=["Order Promotions"])
app.include_router(order_inventory_router, prefix="/api/v1", tags=["Order Inventory Integration"])
app.include_router(customer_tracking_router, prefix="/api/v1/orders", tags=["Customer Order Tracking"])
app.include_router(manual_review_router, prefix="/api/v1/orders", tags=["Manual Order Review"])
app.include_router(order_sync_router)
app.include_router(order_pos_sync_router)
app.include_router(external_pos_webhook_router)
app.include_router(webhook_monitoring_router)
app.include_router(webhook_router)

# Tax Management
app.include_router(tax_router)
app.include_router(tax_calculation_router, prefix="/api/v1/tax", tags=["Tax Calculations"])
app.include_router(tax_compliance_router, prefix="/api/v1/tax", tags=["Tax Compliance"])
app.include_router(tax_jurisdiction_router, prefix="/api/v1/tax", tags=["Tax Jurisdictions"])

# Payroll Management (Phase 3)
app.include_router(payroll_router)  # Phase 3 payroll module routes
app.include_router(payroll_config_router, prefix="/api/v1/payroll", tags=["Payroll Configuration"])
app.include_router(overtime_rules_router, prefix="/api/v1/payroll", tags=["Overtime Rules"])
app.include_router(pay_policy_router, prefix="/api/v1/payroll", tags=["Pay Policies"])
app.include_router(payment_export_router, prefix="/api/v1/payroll", tags=["Payment Export"])
app.include_router(payment_history_router, prefix="/api/v1/payroll", tags=["Payment History"])
app.include_router(payment_routes_router, prefix="/api/v1/payroll", tags=["Payroll Payments"])
app.include_router(payment_summary_router, prefix="/api/v1/payroll", tags=["Payment Summary"])
app.include_router(role_pay_rates_router, prefix="/api/v1/payroll", tags=["Role Pay Rates"])
app.include_router(payroll_tax_calc_router, prefix="/api/v1/payroll", tags=["Payroll Tax Calculations"])

# Settings & POS
app.include_router(settings_router)
app.include_router(settings_ui_router)
app.include_router(pos_sync_router)
app.include_router(pos_router)
app.include_router(pos_migration_router, tags=["POS Migration"])  # AI-powered POS migration suite

# Menu Management
app.include_router(menu_router)
app.include_router(menu_inventory_router)
app.include_router(menu_versioning_router)
app.include_router(recipe_router, prefix="/api/v1/menu", tags=["Recipe Management"])
app.include_router(recipe_router_optimized, prefix="/api/v1/menu", tags=["Recipe Management - Optimized"])
app.include_router(menu_recommendation_router, prefix="/api/v1", tags=["Menu Recommendations"])

# Inventory Management
app.include_router(inventory_management_router)
app.include_router(vendor_management_router)

# Equipment Management
app.include_router(equipment_router, prefix="/api/v1", tags=["Equipment Management"])

# Analytics & Insights
app.include_router(analytics_router)
app.include_router(realtime_analytics_router)
app.include_router(ai_insights_router)
app.include_router(ai_chat_router, prefix="/api/v1/analytics", tags=["AI Chat Analytics"])
app.include_router(predictive_analytics_router, prefix="/api/v1/analytics", tags=["Predictive Analytics"])
app.include_router(pos_analytics_router)

# AI Recommendations
app.include_router(ai_recommendations_router)
app.include_router(admin_insights_router, prefix="/api/v1/ai", tags=["Admin AI Insights"])
app.include_router(ai_pricing_router, prefix="/api/v1/ai", tags=["AI Pricing Recommendations"])
app.include_router(ai_staffing_router, prefix="/api/v1/ai", tags=["AI Staffing Recommendations"])

# Customer Management
app.include_router(customer_router)

# Customer Management V2 - Standardized Response Format
from modules.customers.routers.customer_router_v2 import router as customer_router_v2
app.include_router(customer_router_v2)
app.include_router(customer_segment_router)

# GDPR Compliance
app.include_router(gdpr_router)

# Health Monitoring
app.include_router(health_router)

# Reservations & Waitlist (Enhanced System)
app.include_router(enhanced_reservation_router, prefix="/api/v1", tags=["Reservations"])

# Payments
app.include_router(payment_router, prefix="/api/v1/payments", tags=["Payments"])

# Feedback & Reviews
app.include_router(feedback_router, prefix="/api/v1", tags=["Customer Feedback"])
app.include_router(reviews_router, prefix="/api/v1", tags=["Customer Reviews"])

# SMS Notifications
from modules.sms.routers import sms_router, template_router, opt_out_router, webhook_router as sms_webhook_router
app.include_router(sms_router, tags=["SMS Notifications"])
app.include_router(template_router, tags=["SMS Templates"])
app.include_router(opt_out_router, tags=["SMS Opt-Out"])
app.include_router(sms_webhook_router, tags=["SMS Webhooks"])

# Email Notifications
from modules.email.routes.email_routes import router as email_router
from modules.email.routes.template_routes import router as email_template_router
from modules.email.routes.unsubscribe_routes import router as email_unsubscribe_router
from modules.email.routes.tracking_routes import router as email_tracking_router
from modules.email.routes.webhook_routes import router as email_webhook_router
app.include_router(email_router, prefix="/api/v1/email", tags=["Email Notifications"])
app.include_router(email_template_router, prefix="/api/v1/email", tags=["Email Templates"])
app.include_router(email_unsubscribe_router, prefix="/api/v1/email", tags=["Email Unsubscribe"])
app.include_router(email_tracking_router, prefix="/api/v1/email", tags=["Email Tracking"])
app.include_router(email_webhook_router, prefix="/api/v1/email", tags=["Email Webhooks"])

# Loyalty & Rewards
app.include_router(rewards_router, prefix="/api/v1", tags=["Loyalty & Rewards"])

# Table Management
app.include_router(table_layout_router, prefix="/api/v1", tags=["Table Layout Management"])
app.include_router(table_state_router, prefix="/api/v1", tags=["Table State Management"])
app.include_router(table_analytics_router, prefix="/api/v1/tables", tags=["Table Analytics"])
app.include_router(table_websocket_router, prefix="/api/v1/tables", tags=["Table WebSocket"])

# Promotions & Marketing
app.include_router(promotion_router, prefix="/api/v1", tags=["Promotions"])
app.include_router(ab_testing_router, prefix="/api/v1/promotions", tags=["A/B Testing"])
app.include_router(promotion_analytics_router, prefix="/api/v1/promotions", tags=["Promotion Analytics"])
app.include_router(automation_router, prefix="/api/v1/promotions", tags=["Marketing Automation"])
app.include_router(coupon_router, prefix="/api/v1/promotions", tags=["Coupons"])
app.include_router(referral_router, prefix="/api/v1/promotions", tags=["Referral Program"])
app.include_router(promotion_scheduling_router, prefix="/api/v1/promotions", tags=["Promotion Scheduling"])

# Initialize menu versioning triggers
init_versioning_triggers()


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    # Run startup validation checks
    passed, warnings = run_startup_checks()
    
    # Initialize security services
    from core.auth_rate_limiter import AuthRateLimiter
    from core.audit_logger import audit_logger
    from core.webhook_security import webhook_validator
    from core.config import get_settings
    
    settings = get_settings()
    
    # Initialize auth rate limiter
    app.state.auth_rate_limiter = AuthRateLimiter(
        redis_url=getattr(settings, 'redis_url', None)
    )
    await app.state.auth_rate_limiter.initialize()
    
    # Initialize audit logger
    await audit_logger.initialize(settings.database_url)
    
    # Initialize webhook validator
    app.state.webhook_validator = webhook_validator
    
    # Start order sync scheduler
    await start_sync_scheduler()
    # Start webhook retry scheduler
    await start_webhook_retry_scheduler()
    # Start pricing rule worker
    await start_pricing_rule_worker()
    # Start queue monitor
    await start_queue_monitor()
    # Start priority monitor
    await start_priority_monitor()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    # Close audit logger
    from core.audit_logger import audit_logger
    await audit_logger.close()
    
    # Stop order sync scheduler
    await stop_sync_scheduler()
    # Stop webhook retry scheduler
    await stop_webhook_retry_scheduler()
    # Stop pricing rule worker
    await stop_pricing_rule_worker()
    # Stop queue monitor
    await stop_queue_monitor()
    # Stop priority monitor
    await stop_priority_monitor()


@app.get("/")
def read_root():
    return {"message": "AuraConnect backend is running"}


# Debug endpoints protected by decorator
from core.security_config import protect_debug_endpoint

@app.get("/debug/token")
@protect_debug_endpoint(allowed_envs=["development"])
async def debug_token(authorization: Optional[str] = Depends(HTTPBearer(auto_error=False))):
    """Debug endpoint for token verification - Only available in development"""
    from core.auth import verify_token
    
    if not authorization:
        return {"error": "No authorization header"}
    
    token = authorization.credentials
    
    try:
        from jose import jwt
        # Decode without verification to see the payload
        payload_unverified = jwt.get_unverified_claims(token)
        
        # Now try with verification
        try:
            token_data = verify_token(token)
            
            return {
                "status": "success",
                "payload": payload_unverified,
                "token_valid": True,
                "user_id": token_data.user_id if token_data else None
            }
        except Exception as e:
            return {
                "status": "verification_failed",
                "payload": payload_unverified,
                "error": str(e)
            }
    except Exception as e:
        return {
            "status": "decode_failed",
            "error": str(e)
        }