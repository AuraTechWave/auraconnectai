# backend/modules/email/services/order_email_service.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from modules.email.services.email_service import EmailService
from modules.email.schemas.email_schemas import EmailSendRequest
from modules.orders.models.order_models import Order, OrderItem
from modules.customers.models.customer_models import Customer
from core.config import settings

logger = logging.getLogger(__name__)


class OrderEmailService:
    """Service for sending order-related emails"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService(db)
    
    async def send_order_confirmation(self, order_id: int) -> bool:
        """
        Send order confirmation email
        
        Args:
            order_id: Order ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            # Get order with related data
            order = self.db.query(Order).filter(Order.id == order_id).first()
            
            if not order:
                logger.error(f"Order {order_id} not found")
                return False
            
            # Get customer info
            customer = None
            if order.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == order.customer_id
                ).first()
            
            if not customer or not customer.email:
                logger.warning(f"No customer email for order {order_id}")
                return False
            
            # Get order items
            order_items = self.db.query(OrderItem).filter(
                OrderItem.order_id == order_id
            ).all()
            
            # Prepare template variables
            template_vars = self._prepare_order_template_vars(order, customer, order_items)
            
            # Send email
            email_request = EmailSendRequest(
                to_email=customer.email,
                to_name=customer.name,
                template_id=self._get_template_id("order_confirmation"),
                template_variables=template_vars,
                customer_id=customer.id,
                order_id=order.id,
                tags=["order", "confirmation"],
                metadata={
                    "order_number": order.order_number,
                    "order_type": order.order_type
                }
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent order confirmation email for order {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending order confirmation email: {str(e)}")
            return False
    
    async def send_order_ready_notification(self, order_id: int) -> bool:
        """
        Send notification that order is ready for pickup
        
        Args:
            order_id: Order ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            order = self.db.query(Order).filter(Order.id == order_id).first()
            
            if not order or not order.customer_id:
                return False
            
            customer = self.db.query(Customer).filter(
                Customer.id == order.customer_id
            ).first()
            
            if not customer or not customer.email:
                return False
            
            # Prepare template variables
            template_vars = {
                "customer_name": customer.name,
                "order_number": order.order_number,
                "pickup_time": datetime.now().strftime("%I:%M %p"),
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_address": settings.RESTAURANT_ADDRESS,
                "restaurant_phone": settings.RESTAURANT_PHONE
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=customer.email,
                to_name=customer.name,
                subject=f"Your order #{order.order_number} is ready!",
                html_body=self._generate_order_ready_html(template_vars),
                text_body=self._generate_order_ready_text(template_vars),
                customer_id=customer.id,
                order_id=order.id,
                tags=["order", "ready"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent order ready email for order {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending order ready email: {str(e)}")
            return False
    
    async def send_order_cancelled_notification(
        self, 
        order_id: int, 
        reason: Optional[str] = None
    ) -> bool:
        """
        Send order cancellation notification
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
        
        Returns:
            True if email was sent successfully
        """
        try:
            order = self.db.query(Order).filter(Order.id == order_id).first()
            
            if not order or not order.customer_id:
                return False
            
            customer = self.db.query(Customer).filter(
                Customer.id == order.customer_id
            ).first()
            
            if not customer or not customer.email:
                return False
            
            # Prepare template variables
            template_vars = {
                "customer_name": customer.name,
                "order_number": order.order_number,
                "cancellation_reason": reason or "Order cancelled by restaurant",
                "refund_amount": float(order.total_amount),
                "refund_timeframe": "3-5 business days",
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_phone": settings.RESTAURANT_PHONE,
                "restaurant_email": settings.RESTAURANT_EMAIL
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=customer.email,
                to_name=customer.name,
                subject=f"Order #{order.order_number} Cancelled",
                html_body=self._generate_order_cancelled_html(template_vars),
                text_body=self._generate_order_cancelled_text(template_vars),
                customer_id=customer.id,
                order_id=order.id,
                tags=["order", "cancelled"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent order cancelled email for order {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending order cancelled email: {str(e)}")
            return False
    
    def _prepare_order_template_vars(
        self, 
        order: Order, 
        customer: Customer, 
        order_items: list
    ) -> Dict[str, Any]:
        """Prepare template variables for order emails"""
        
        # Format order items for template
        items_data = []
        for item in order_items:
            item_data = {
                "quantity": item.quantity,
                "name": item.name,
                "modifiers": item.modifiers,
                "total": float(item.total_price)
            }
            items_data.append(item_data)
        
        # Calculate estimated ready time
        if order.order_type == "pickup":
            estimated_ready = (order.created_at.replace(tzinfo=None) + 
                             timedelta(minutes=30)).strftime("%I:%M %p")
        else:
            estimated_ready = (order.created_at.replace(tzinfo=None) + 
                             timedelta(minutes=45)).strftime("%I:%M %p")
        
        return {
            "customer_name": customer.name,
            "order_number": order.order_number,
            "order_date": order.created_at.strftime("%B %d, %Y at %I:%M %p"),
            "estimated_ready_time": estimated_ready,
            "order_items": items_data,
            "subtotal": float(order.subtotal),
            "tax_amount": float(order.tax_amount),
            "delivery_fee": float(order.delivery_fee) if order.delivery_fee else None,
            "total_amount": float(order.total_amount),
            "delivery_address": order.delivery_address,
            "special_instructions": order.special_instructions,
            "order_tracking_url": f"{settings.APP_URL}/orders/{order.order_number}",
            "restaurant_name": settings.RESTAURANT_NAME,
            "restaurant_address": settings.RESTAURANT_ADDRESS,
            "restaurant_phone": settings.RESTAURANT_PHONE,
            "restaurant_email": settings.RESTAURANT_EMAIL,
            "current_year": datetime.now().year
        }
    
    def _get_template_id(self, template_name: str) -> int:
        """Get template ID by name"""
        from modules.email.models.email_models import EmailTemplate
        
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.name == template_name
        ).first()
        
        if template:
            return template.id
        
        # If template doesn't exist, we should create it from base_templates
        # This is a fallback - in production, templates should be seeded
        raise ValueError(f"Email template '{template_name}' not found")
    
    def _generate_order_ready_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for order ready email"""
        return f"""
        <h2>Your order is ready for pickup! 🎉</h2>
        <p>Hi {vars['customer_name']},</p>
        <p>Great news! Your order <strong>#{vars['order_number']}</strong> is ready for pickup.</p>
        
        <div style="background-color: #d4edda; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Pickup Information</h3>
            <p><strong>Order Number:</strong> #{vars['order_number']}<br>
            <strong>Ready at:</strong> {vars['pickup_time']}<br>
            <strong>Location:</strong> {vars['restaurant_name']}<br>
            {vars['restaurant_address']}</p>
        </div>
        
        <p>Please bring your order number when picking up your order.</p>
        <p>Questions? Call us at {vars['restaurant_phone']}</p>
        <p>Thank you for choosing {vars['restaurant_name']}!</p>
        """
    
    def _generate_order_ready_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for order ready email"""
        return f"""
        Your order is ready for pickup!
        
        Hi {vars['customer_name']},
        
        Great news! Your order #{vars['order_number']} is ready for pickup.
        
        PICKUP INFORMATION
        Order Number: #{vars['order_number']}
        Ready at: {vars['pickup_time']}
        Location: {vars['restaurant_name']}
        {vars['restaurant_address']}
        
        Please bring your order number when picking up your order.
        
        Questions? Call us at {vars['restaurant_phone']}
        
        Thank you for choosing {vars['restaurant_name']}!
        """
    
    def _generate_order_cancelled_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for order cancelled email"""
        return f"""
        <h2>Order Cancellation Notice</h2>
        <p>Hi {vars['customer_name']},</p>
        <p>We're sorry to inform you that your order <strong>#{vars['order_number']}</strong> has been cancelled.</p>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Cancellation Details</h3>
            <p><strong>Order Number:</strong> #{vars['order_number']}<br>
            <strong>Reason:</strong> {vars['cancellation_reason']}<br>
            <strong>Refund Amount:</strong> ${vars['refund_amount']:.2f}<br>
            <strong>Refund Timeframe:</strong> {vars['refund_timeframe']}</p>
        </div>
        
        <p>The refund will be processed to your original payment method.</p>
        <p>We apologize for any inconvenience this may have caused.</p>
        <p>If you have any questions, please contact us at {vars['restaurant_phone']} or {vars['restaurant_email']}</p>
        <p>Thank you for your understanding.</p>
        """
    
    def _generate_order_cancelled_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for order cancelled email"""
        return f"""
        Order Cancellation Notice
        
        Hi {vars['customer_name']},
        
        We're sorry to inform you that your order #{vars['order_number']} has been cancelled.
        
        CANCELLATION DETAILS
        Order Number: #{vars['order_number']}
        Reason: {vars['cancellation_reason']}
        Refund Amount: ${vars['refund_amount']:.2f}
        Refund Timeframe: {vars['refund_timeframe']}
        
        The refund will be processed to your original payment method.
        
        We apologize for any inconvenience this may have caused.
        
        If you have any questions, please contact us at {vars['restaurant_phone']} or {vars['restaurant_email']}
        
        Thank you for your understanding.
        """