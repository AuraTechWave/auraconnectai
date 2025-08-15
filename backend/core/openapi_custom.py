# backend/core/openapi_custom.py

"""
Custom OpenAPI schema generation with enhanced documentation.
Provides comprehensive API documentation following OpenAPI 3.0 specification.
"""

from typing import Dict, Any, Optional, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced documentation.

    Args:
        app: FastAPI application instance

    Returns:
        OpenAPI schema dictionary
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=[
            {"url": "http://localhost:8000", "description": "Local development server"},
            {
                "url": "https://api-staging.auraconnect.ai",
                "description": "Staging server",
            },
            {"url": "https://api.auraconnect.ai", "description": "Production server"},
        ],
    )

    # Add enhanced documentation
    openapi_schema["info"]["x-logo"] = {
        "url": "https://auraconnect.ai/assets/logo.png",
        "altText": "AuraConnect Logo",
    }

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT authentication token obtained from /auth/login endpoint",
        },
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for server-to-server authentication",
        },
    }

    # Add common response schemas
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "example": "VALIDATION_ERROR"},
                    "message": {"type": "string", "example": "Invalid request data"},
                    "details": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                    },
                    "request_id": {"type": "string", "example": "req_xyz789"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
                "required": ["code", "message"],
            }
        },
        "required": ["error"],
    }

    openapi_schema["components"]["schemas"]["PaginationMeta"] = {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "example": 1},
            "page_size": {"type": "integer", "example": 20},
            "total_pages": {"type": "integer", "example": 5},
            "total_count": {"type": "integer", "example": 98},
            "has_next": {"type": "boolean", "example": True},
            "has_previous": {"type": "boolean", "example": False},
        },
    }

    # Add common parameters
    openapi_schema["components"]["parameters"] = {
        "PageParam": {
            "name": "page",
            "in": "query",
            "description": "Page number for pagination",
            "required": False,
            "schema": {"type": "integer", "default": 1, "minimum": 1},
        },
        "PageSizeParam": {
            "name": "page_size",
            "in": "query",
            "description": "Number of items per page",
            "required": False,
            "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
        },
        "SearchParam": {
            "name": "search",
            "in": "query",
            "description": "Search query for filtering results",
            "required": False,
            "schema": {"type": "string"},
        },
        "SortByParam": {
            "name": "sort_by",
            "in": "query",
            "description": "Field to sort results by",
            "required": False,
            "schema": {"type": "string", "default": "created_at"},
        },
        "SortOrderParam": {
            "name": "sort_order",
            "in": "query",
            "description": "Sort order direction",
            "required": False,
            "schema": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
        },
    }

    # Add tags with descriptions
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "Authentication and authorization endpoints",
            "externalDocs": {
                "description": "Authentication guide",
                "url": "https://docs.auraconnect.ai/auth",
            },
        },
        {
            "name": "Staff Management",
            "description": "Employee management, scheduling, and attendance tracking",
            "externalDocs": {
                "description": "Staff management guide",
                "url": "https://docs.auraconnect.ai/staff",
            },
        },
        {
            "name": "Orders",
            "description": "Order creation, management, and tracking",
            "externalDocs": {
                "description": "Orders API reference",
                "url": "https://docs.auraconnect.ai/api/orders",
            },
        },
        {
            "name": "Menu Management",
            "description": "Menu items, categories, modifiers, and recipes",
            "externalDocs": {
                "description": "Menu management guide",
                "url": "https://docs.auraconnect.ai/menu",
            },
        },
        {
            "name": "Inventory",
            "description": "Inventory tracking, stock management, and vendor integration",
            "externalDocs": {
                "description": "Inventory guide",
                "url": "https://docs.auraconnect.ai/inventory",
            },
        },
        {
            "name": "Payroll",
            "description": "Payroll processing, tax calculations, and payment management",
            "externalDocs": {
                "description": "Payroll documentation",
                "url": "https://docs.auraconnect.ai/payroll",
            },
        },
        {
            "name": "Analytics",
            "description": "Business analytics, reports, and AI-powered insights",
            "externalDocs": {
                "description": "Analytics guide",
                "url": "https://docs.auraconnect.ai/analytics",
            },
        },
        {
            "name": "Customer Management",
            "description": "Customer profiles, loyalty programs, and feedback",
            "externalDocs": {
                "description": "Customer management guide",
                "url": "https://docs.auraconnect.ai/customers",
            },
        },
        {
            "name": "POS Integration",
            "description": "Point of Sale system integrations and synchronization",
            "externalDocs": {
                "description": "POS integration guide",
                "url": "https://docs.auraconnect.ai/pos",
            },
        },
        {
            "name": "Payments",
            "description": "Payment processing, refunds, and reconciliation",
            "externalDocs": {
                "description": "Payments guide",
                "url": "https://docs.auraconnect.ai/payments",
            },
        },
    ]

    # Add webhook documentation
    openapi_schema["webhooks"] = {
        "orderCreated": {
            "post": {
                "summary": "Order Created",
                "description": "Triggered when a new order is created",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {
                                        "type": "string",
                                        "example": "order.created",
                                    },
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time",
                                    },
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "order_number": {"type": "string"},
                                            "total_amount": {"type": "string"},
                                        },
                                    },
                                },
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Webhook processed successfully"}},
            }
        },
        "paymentCompleted": {
            "post": {
                "summary": "Payment Completed",
                "description": "Triggered when a payment is successfully processed",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {
                                        "type": "string",
                                        "example": "payment.completed",
                                    },
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time",
                                    },
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "payment_id": {"type": "string"},
                                            "order_id": {"type": "integer"},
                                            "amount": {"type": "string"},
                                            "payment_method": {"type": "string"},
                                        },
                                    },
                                },
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "Webhook processed successfully"}},
            }
        },
    }

    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "AuraConnect API Documentation",
        "url": "https://docs.auraconnect.ai/api",
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def configure_openapi_ui(app: FastAPI):
    """
    Configure custom OpenAPI UI endpoints with enhanced styling.

    Args:
        app: FastAPI application instance
    """

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_ui_parameters={
                "deepLinking": True,
                "persistAuthorization": True,
                "displayOperationId": True,
                "defaultModelsExpandDepth": 1,
                "defaultModelExpandDepth": 1,
                "displayRequestDuration": True,
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
                "tryItOutEnabled": True,
                "supportedSubmitMethods": [
                    "get",
                    "put",
                    "post",
                    "delete",
                    "options",
                    "head",
                    "patch",
                    "trace",
                ],
                "validatorUrl": None,
                "onComplete": """() => {
                    // Add custom styling
                    const style = document.createElement('style');
                    style.innerHTML = `
                        .swagger-ui .topbar { background-color: #1a1a2e; }
                        .swagger-ui .topbar .download-url-wrapper { display: none; }
                        .swagger-ui .info .title { color: #16213e; }
                        .swagger-ui .scheme-container { background: #f5f5f5; padding: 15px; }
                    `;
                    document.head.appendChild(style);
                }""",
            },
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            redoc_favicon_url="https://auraconnect.ai/favicon.ico",
            with_google_fonts=True,
        )


def add_operation_ids(app: FastAPI):
    """
    Add operation IDs to all routes for better API client generation.

    Args:
        app: FastAPI application instance
    """
    for route in app.routes:
        if hasattr(route, "endpoint") and hasattr(route, "methods"):
            # Generate operation ID from endpoint name
            operation_id = route.endpoint.__name__

            # Make it more descriptive based on HTTP method
            for method in route.methods:
                if method == "GET":
                    if "{" in route.path:
                        route.operation_id = f"get_{operation_id}_by_id"
                    else:
                        route.operation_id = f"list_{operation_id}"
                elif method == "POST":
                    route.operation_id = f"create_{operation_id}"
                elif method == "PUT":
                    route.operation_id = f"update_{operation_id}"
                elif method == "DELETE":
                    route.operation_id = f"delete_{operation_id}"
                elif method == "PATCH":
                    route.operation_id = f"patch_{operation_id}"
