# backend/modules/payments/api/payment_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from decimal import Decimal
import logging

from core.database import get_db
from core.deps import get_current_user
from core.permissions import Permission, require_permissions
from ..models.payment_models import (
    Payment, Refund, CustomerPaymentMethod,
    PaymentGateway, PaymentStatus
)
from ..services import payment_service, webhook_service
from ..schemas.payment_schemas import (
    PaymentCreate, PaymentResponse, PaymentDetail,
    RefundCreate, RefundResponse,
    PaymentMethodCreate, PaymentMethodResponse,
    PaymentGatewayConfig, PaymentWebhookResponse
)
from ...auth.models.user_models import User
from ...orders.models.order_models import Order


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=PaymentResponse)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new payment for an order
    
    Required permissions: order.payment.create
    """
    await require_permissions(current_user, Permission.ORDER_PAYMENT_CREATE)
    
    # Verify order access
    order = await db.get(Order, payment_data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check order ownership or staff permission
    if order.customer_id != current_user.id:
        await require_permissions(current_user, Permission.ORDER_VIEW_ALL)
    
    # Validate order can be paid
    if order.payment_status == 'paid':
        raise HTTPException(status_code=400, detail="Order already paid")
    
    # Create payment
    try:
        payment = await payment_service.create_payment(
            db=db,
            order_id=payment_data.order_id,
            gateway=payment_data.gateway,
            amount=payment_data.amount or order.total_amount,
            currency=payment_data.currency,
            payment_method_id=payment_data.payment_method_id,
            save_payment_method=payment_data.save_payment_method,
            return_url=payment_data.return_url,
            metadata=payment_data.metadata
        )
        
        # Get gateway config for frontend
        gateway_config = payment_service.get_public_gateway_config(payment.gateway)
        
        return PaymentResponse(
            id=payment.id,
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            gateway=payment.gateway,
            gateway_payment_id=payment.gateway_payment_id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            payment_method=payment.method,
            requires_action=payment.metadata.get('requires_action', False),
            action_url=payment.metadata.get('action_url'),
            gateway_config=gateway_config,
            created_at=payment.created_at
        )
        
    except Exception as e:
        logger.error(f"Payment creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{payment_id}/capture", response_model=PaymentResponse)
async def capture_payment(
    payment_id: int,
    amount: Optional[Decimal] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Capture a previously authorized payment
    
    Required permissions: order.payment.create
    """
    await require_permissions(current_user, Permission.ORDER_PAYMENT_CREATE)
    
    # Get payment
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify access
    order = await db.get(Order, payment.order_id)
    if order.customer_id != current_user.id:
        await require_permissions(current_user, Permission.ORDER_VIEW_ALL)
    
    # Capture payment
    try:
        payment = await payment_service.capture_payment(db, payment_id, amount)
        
        return PaymentResponse(
            id=payment.id,
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            gateway=payment.gateway,
            gateway_payment_id=payment.gateway_payment_id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            payment_method=payment.method,
            created_at=payment.created_at
        )
        
    except Exception as e:
        logger.error(f"Payment capture failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    payment_id: int,
    reason: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a pending payment
    
    Required permissions: order.payment.create
    """
    await require_permissions(current_user, Permission.ORDER_PAYMENT_CREATE)
    
    # Get payment
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify access
    order = await db.get(Order, payment.order_id)
    if order.customer_id != current_user.id:
        await require_permissions(current_user, Permission.ORDER_VIEW_ALL)
    
    # Cancel payment
    try:
        payment = await payment_service.cancel_payment(db, payment_id, reason)
        
        return PaymentResponse(
            id=payment.id,
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            gateway=payment.gateway,
            gateway_payment_id=payment.gateway_payment_id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            payment_method=payment.method,
            created_at=payment.created_at
        )
        
    except Exception as e:
        logger.error(f"Payment cancellation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}", response_model=PaymentDetail)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get payment details
    
    Required permissions: order.view (own) or order.view.all
    """
    # Get payment with relations
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify access
    order = await db.get(Order, payment.order_id)
    if order.customer_id != current_user.id:
        await require_permissions(current_user, Permission.ORDER_VIEW_ALL)
    
    # Get refunds
    result = await db.execute(
        select(Refund).where(Refund.payment_id == payment_id)
    )
    refunds = result.scalars().all()
    
    return PaymentDetail(
        id=payment.id,
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        gateway=payment.gateway,
        gateway_payment_id=payment.gateway_payment_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        payment_method=payment.method,
        payment_method_details=payment.payment_method_details,
        fee_amount=payment.fee_amount,
        net_amount=payment.net_amount,
        processed_at=payment.processed_at,
        failure_code=payment.failure_code,
        failure_message=payment.failure_message,
        refunds=[
            RefundResponse(
                id=r.id,
                refund_id=r.refund_id,
                payment_id=r.payment_id,
                amount=r.amount,
                currency=r.currency,
                status=r.status,
                reason=r.reason,
                processed_at=r.processed_at,
                created_at=r.created_at
            ) for r in refunds
        ],
        created_at=payment.created_at,
        updated_at=payment.updated_at
    )


@router.post("/{payment_id}/refund", response_model=RefundResponse)
async def create_refund(
    payment_id: int,
    refund_data: RefundCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a refund for a payment
    
    Required permissions: order.refund.create
    """
    await require_permissions(current_user, Permission.ORDER_REFUND_CREATE)
    
    # Get payment
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Create refund
    try:
        refund = await payment_service.create_refund(
            db=db,
            payment_id=payment_id,
            amount=refund_data.amount,
            reason=refund_data.reason,
            initiated_by=current_user.id,
            metadata=refund_data.metadata
        )
        
        return RefundResponse(
            id=refund.id,
            refund_id=refund.refund_id,
            payment_id=refund.payment_id,
            gateway_refund_id=refund.gateway_refund_id,
            amount=refund.amount,
            currency=refund.currency,
            status=refund.status,
            reason=refund.reason,
            processed_at=refund.processed_at,
            created_at=refund.created_at
        )
        
    except Exception as e:
        logger.error(f"Refund creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund(
    refund_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get refund details
    
    Required permissions: order.view (own) or order.view.all
    """
    # Get refund
    refund = await db.get(Refund, refund_id)
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    
    # Get payment and order for access check
    payment = await db.get(Payment, refund.payment_id)
    order = await db.get(Order, payment.order_id)
    
    if order.customer_id != current_user.id:
        await require_permissions(current_user, Permission.ORDER_VIEW_ALL)
    
    return RefundResponse(
        id=refund.id,
        refund_id=refund.refund_id,
        payment_id=refund.payment_id,
        gateway_refund_id=refund.gateway_refund_id,
        amount=refund.amount,
        currency=refund.currency,
        status=refund.status,
        reason=refund.reason,
        processed_at=refund.processed_at,
        failure_code=refund.failure_code,
        failure_message=refund.failure_message,
        created_at=refund.created_at
    )


@router.post("/methods/save", response_model=PaymentMethodResponse)
async def save_payment_method(
    method_data: PaymentMethodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save a payment method for future use
    
    Customers can only save their own payment methods
    """
    # Customers can only save their own payment methods
    if method_data.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot save payment methods for other customers")
    
    try:
        payment_method = await payment_service.save_payment_method(
            db=db,
            customer_id=method_data.customer_id,
            gateway=method_data.gateway,
            payment_method_token=method_data.payment_method_token,
            set_as_default=method_data.set_as_default,
            metadata=method_data.metadata
        )
        
        return PaymentMethodResponse(
            id=payment_method.id,
            customer_id=payment_method.customer_id,
            gateway=payment_method.gateway,
            method_type=payment_method.method_type,
            display_name=payment_method.display_name,
            card_last4=payment_method.card_last4,
            card_brand=payment_method.card_brand,
            card_exp_month=payment_method.card_exp_month,
            card_exp_year=payment_method.card_exp_year,
            is_default=payment_method.is_default,
            is_active=payment_method.is_active,
            created_at=payment_method.created_at
        )
        
    except Exception as e:
        logger.error(f"Save payment method failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/methods/list", response_model=List[PaymentMethodResponse])
async def list_payment_methods(
    gateway: Optional[PaymentGateway] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List saved payment methods for the current user
    """
    payment_methods = await payment_service.list_customer_payment_methods(
        db=db,
        customer_id=current_user.id,
        gateway=gateway,
        active_only=True
    )
    
    return [
        PaymentMethodResponse(
            id=pm.id,
            customer_id=pm.customer_id,
            gateway=pm.gateway,
            method_type=pm.method_type,
            display_name=pm.display_name,
            card_last4=pm.card_last4,
            card_brand=pm.card_brand,
            card_exp_month=pm.card_exp_month,
            card_exp_year=pm.card_exp_year,
            is_default=pm.is_default,
            is_active=pm.is_active,
            created_at=pm.created_at
        ) for pm in payment_methods
    ]


@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a saved payment method
    """
    # Get payment method
    payment_method = await db.get(CustomerPaymentMethod, method_id)
    if not payment_method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    # Verify ownership
    if payment_method.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete payment methods for other customers")
    
    success = await payment_service.delete_payment_method(db, method_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete payment method")
    
    return {"status": "success", "message": "Payment method deleted"}


@router.get("/gateways/available", response_model=List[PaymentGatewayConfig])
async def get_available_gateways(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available payment gateways and their configuration
    """
    gateways = payment_service.get_available_gateways()
    
    return [
        PaymentGatewayConfig(
            gateway=gateway,
            config=payment_service.get_public_gateway_config(gateway)
        ) for gateway in gateways
    ]


@router.post("/webhook/{gateway}", response_model=PaymentWebhookResponse)
async def handle_webhook(
    gateway: PaymentGateway,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming webhooks from payment gateways
    
    This endpoint is called by payment gateways and doesn't require authentication
    """
    try:
        # Get headers and body
        headers = dict(request.headers)
        body = await request.body()
        
        # Import webhook queue service
        from ..services.webhook_queue_service import webhook_queue_service
        
        # Queue webhook for background processing
        job_id = await webhook_queue_service.queue_webhook(
            gateway=gateway,
            headers=headers,
            body=body,
            priority=3  # High priority for payment webhooks
        )
        
        # Return immediately with accepted status
        return PaymentWebhookResponse(
            status="accepted",
            message=f"Webhook queued for processing: {job_id}"
        )
        
    except Exception as e:
        logger.error(f"Webhook queueing error for {gateway}: {e}")
        
        # Fallback to inline processing if queueing fails
        try:
            result = await webhook_service.process_webhook(
                db=db,
                gateway=gateway,
                headers=headers,
                body=body
            )
            return PaymentWebhookResponse(**result)
        except:
            # Return success to prevent retries for bad webhooks
            return PaymentWebhookResponse(
                status="error",
                message=str(e)
            )


@router.post("/{payment_id}/sync")
async def sync_payment_status(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually sync payment status with gateway
    
    Required permissions: order.payment.create
    """
    await require_permissions(current_user, Permission.ORDER_PAYMENT_CREATE)
    
    try:
        payment = await payment_service.sync_payment_status(db, payment_id)
        
        return {
            "status": "success",
            "payment_status": payment.status,
            "message": "Payment status synchronized"
        }
        
    except Exception as e:
        logger.error(f"Payment sync failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))