# backend/modules/email/services/reservation_email_service.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import random
import string

from modules.email.services.email_service import EmailService
from modules.email.schemas.email_schemas import EmailSendRequest
from modules.reservations.models.reservation_models import Reservation
from modules.customers.models.customer_models import Customer
from core.config import settings

logger = logging.getLogger(__name__)


class ReservationEmailService:
    """Service for sending reservation-related emails"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService(db)
    
    async def send_reservation_confirmation(self, reservation_id: int) -> bool:
        """
        Send reservation confirmation email
        
        Args:
            reservation_id: Reservation ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            # Get reservation with related data
            reservation = self.db.query(Reservation).filter(
                Reservation.id == reservation_id
            ).first()
            
            if not reservation:
                logger.error(f"Reservation {reservation_id} not found")
                return False
            
            # Get customer info
            customer = None
            if reservation.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == reservation.customer_id
                ).first()
            
            # Use guest email if no customer
            email = None
            name = None
            if customer:
                email = customer.email
                name = customer.name
            elif reservation.guest_email:
                email = reservation.guest_email
                name = reservation.guest_name
            
            if not email:
                logger.warning(f"No email for reservation {reservation_id}")
                return False
            
            # Generate confirmation code if not exists
            if not reservation.confirmation_code:
                reservation.confirmation_code = self._generate_confirmation_code()
                self.db.commit()
            
            # Prepare template variables
            template_vars = {
                "customer_name": name or "Guest",
                "reservation_date": reservation.reservation_date.strftime("%A, %B %d, %Y"),
                "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
                "party_size": reservation.party_size,
                "confirmation_code": reservation.confirmation_code,
                "special_requests": reservation.special_requests,
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_address": settings.RESTAURANT_ADDRESS,
                "restaurant_phone": settings.RESTAURANT_PHONE,
                "modify_reservation_url": f"{settings.FRONTEND_URL}/reservations/modify/{reservation.confirmation_code}"
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=email,
                to_name=name,
                template_id=self._get_template_id("reservation_confirmation"),
                template_variables=template_vars,
                customer_id=reservation.customer_id,
                reservation_id=reservation.id,
                tags=["reservation", "confirmation"],
                metadata={
                    "confirmation_code": reservation.confirmation_code,
                    "party_size": reservation.party_size
                }
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent reservation confirmation email for reservation {reservation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending reservation confirmation email: {str(e)}")
            return False
    
    async def send_reservation_reminder(self, reservation_id: int) -> bool:
        """
        Send reservation reminder email (typically sent day before)
        
        Args:
            reservation_id: Reservation ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            reservation = self.db.query(Reservation).filter(
                Reservation.id == reservation_id
            ).first()
            
            if not reservation:
                return False
            
            # Get customer info
            customer = None
            email = None
            name = None
            
            if reservation.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == reservation.customer_id
                ).first()
                if customer:
                    email = customer.email
                    name = customer.name
            else:
                email = reservation.guest_email
                name = reservation.guest_name
            
            if not email:
                return False
            
            # Prepare template variables
            template_vars = {
                "customer_name": name or "Guest",
                "reservation_date": reservation.reservation_date.strftime("%A, %B %d, %Y"),
                "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
                "party_size": reservation.party_size,
                "confirmation_code": reservation.confirmation_code,
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_address": settings.RESTAURANT_ADDRESS,
                "restaurant_phone": settings.RESTAURANT_PHONE,
                "modify_reservation_url": f"{settings.FRONTEND_URL}/reservations/modify/{reservation.confirmation_code}",
                "is_tomorrow": reservation.reservation_date == (datetime.now().date() + timedelta(days=1))
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=email,
                to_name=name,
                subject=f"Reminder: Your reservation at {settings.RESTAURANT_NAME} tomorrow",
                html_body=self._generate_reminder_html(template_vars),
                text_body=self._generate_reminder_text(template_vars),
                customer_id=reservation.customer_id,
                reservation_id=reservation.id,
                tags=["reservation", "reminder"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent reservation reminder email for reservation {reservation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending reservation reminder email: {str(e)}")
            return False
    
    async def send_reservation_cancelled(
        self, 
        reservation_id: int,
        reason: Optional[str] = None,
        cancelled_by: str = "customer"
    ) -> bool:
        """
        Send reservation cancellation notification
        
        Args:
            reservation_id: Reservation ID
            reason: Cancellation reason
            cancelled_by: Who cancelled (customer/restaurant)
        
        Returns:
            True if email was sent successfully
        """
        try:
            reservation = self.db.query(Reservation).filter(
                Reservation.id == reservation_id
            ).first()
            
            if not reservation:
                return False
            
            # Get email info
            email = None
            name = None
            
            if reservation.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == reservation.customer_id
                ).first()
                if customer:
                    email = customer.email
                    name = customer.name
            else:
                email = reservation.guest_email
                name = reservation.guest_name
            
            if not email:
                return False
            
            # Prepare template variables
            template_vars = {
                "customer_name": name or "Guest",
                "reservation_date": reservation.reservation_date.strftime("%A, %B %d, %Y"),
                "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
                "party_size": reservation.party_size,
                "confirmation_code": reservation.confirmation_code,
                "cancellation_reason": reason or "Reservation cancelled",
                "cancelled_by": "you" if cancelled_by == "customer" else "the restaurant",
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_phone": settings.RESTAURANT_PHONE,
                "restaurant_email": settings.RESTAURANT_EMAIL,
                "rebooking_url": f"{settings.FRONTEND_URL}/reservations/new"
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=email,
                to_name=name,
                subject=f"Reservation Cancelled - {reservation.confirmation_code}",
                html_body=self._generate_cancellation_html(template_vars),
                text_body=self._generate_cancellation_text(template_vars),
                customer_id=reservation.customer_id,
                reservation_id=reservation.id,
                tags=["reservation", "cancelled"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent reservation cancellation email for reservation {reservation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending reservation cancellation email: {str(e)}")
            return False
    
    async def send_reservation_modified(self, reservation_id: int) -> bool:
        """
        Send notification that reservation was modified
        
        Args:
            reservation_id: Reservation ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            reservation = self.db.query(Reservation).filter(
                Reservation.id == reservation_id
            ).first()
            
            if not reservation:
                return False
            
            # Get email info
            email = None
            name = None
            
            if reservation.customer_id:
                customer = self.db.query(Customer).filter(
                    Customer.id == reservation.customer_id
                ).first()
                if customer:
                    email = customer.email
                    name = customer.name
            else:
                email = reservation.guest_email
                name = reservation.guest_name
            
            if not email:
                return False
            
            # Prepare template variables
            template_vars = {
                "customer_name": name or "Guest",
                "reservation_date": reservation.reservation_date.strftime("%A, %B %d, %Y"),
                "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
                "party_size": reservation.party_size,
                "confirmation_code": reservation.confirmation_code,
                "special_requests": reservation.special_requests,
                "restaurant_name": settings.RESTAURANT_NAME,
                "restaurant_address": settings.RESTAURANT_ADDRESS,
                "restaurant_phone": settings.RESTAURANT_PHONE
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=email,
                to_name=name,
                subject=f"Reservation Updated - {reservation.confirmation_code}",
                html_body=self._generate_modification_html(template_vars),
                text_body=self._generate_modification_text(template_vars),
                customer_id=reservation.customer_id,
                reservation_id=reservation.id,
                tags=["reservation", "modified"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent reservation modification email for reservation {reservation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending reservation modification email: {str(e)}")
            return False
    
    def _generate_confirmation_code(self) -> str:
        """Generate a unique confirmation code"""
        # Generate 6 character alphanumeric code
        characters = string.ascii_uppercase + string.digits
        code = ''.join(random.choice(characters) for _ in range(6))
        
        # Check if code already exists (very unlikely but good practice)
        existing = self.db.query(Reservation).filter(
            Reservation.confirmation_code == code
        ).first()
        
        if existing:
            # Recursively generate a new one
            return self._generate_confirmation_code()
        
        return code
    
    def _get_template_id(self, template_name: str) -> int:
        """Get template ID by name"""
        from modules.email.models.email_models import EmailTemplate
        
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.name == template_name
        ).first()
        
        if template:
            return template.id
        
        raise ValueError(f"Email template '{template_name}' not found")
    
    def _generate_reminder_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for reservation reminder"""
        when = "tomorrow" if vars.get('is_tomorrow') else "soon"
        return f"""
        <h2>Reminder: Your reservation is {when}!</h2>
        <p>Hi {vars['customer_name']},</p>
        <p>This is a friendly reminder about your upcoming reservation at {vars['restaurant_name']}.</p>
        
        <div style="background-color: #d1ecf1; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Reservation Details</h3>
            <p><strong>Date:</strong> {vars['reservation_date']}<br>
            <strong>Time:</strong> {vars['reservation_time']}<br>
            <strong>Party Size:</strong> {vars['party_size']} guests<br>
            <strong>Confirmation Code:</strong> {vars['confirmation_code']}</p>
        </div>
        
        <h3>Location</h3>
        <p>{vars['restaurant_name']}<br>
        {vars['restaurant_address']}<br>
        Phone: {vars['restaurant_phone']}</p>
        
        <p>Need to make changes? <a href="{vars['modify_reservation_url']}">Modify your reservation</a></p>
        
        <p>We look forward to seeing you!</p>
        """
    
    def _generate_reminder_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for reservation reminder"""
        when = "tomorrow" if vars.get('is_tomorrow') else "soon"
        return f"""
        Reminder: Your reservation is {when}!
        
        Hi {vars['customer_name']},
        
        This is a friendly reminder about your upcoming reservation at {vars['restaurant_name']}.
        
        RESERVATION DETAILS
        Date: {vars['reservation_date']}
        Time: {vars['reservation_time']}
        Party Size: {vars['party_size']} guests
        Confirmation Code: {vars['confirmation_code']}
        
        LOCATION
        {vars['restaurant_name']}
        {vars['restaurant_address']}
        Phone: {vars['restaurant_phone']}
        
        Need to make changes? Visit: {vars['modify_reservation_url']}
        
        We look forward to seeing you!
        """
    
    def _generate_cancellation_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for reservation cancellation"""
        return f"""
        <h2>Reservation Cancellation</h2>
        <p>Hi {vars['customer_name']},</p>
        <p>Your reservation has been cancelled by {vars['cancelled_by']}.</p>
        
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Cancelled Reservation Details</h3>
            <p><strong>Date:</strong> {vars['reservation_date']}<br>
            <strong>Time:</strong> {vars['reservation_time']}<br>
            <strong>Party Size:</strong> {vars['party_size']} guests<br>
            <strong>Confirmation Code:</strong> {vars['confirmation_code']}<br>
            <strong>Reason:</strong> {vars['cancellation_reason']}</p>
        </div>
        
        <p>We apologize for any inconvenience.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{vars['rebooking_url']}" style="display: inline-block; padding: 12px 30px; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 5px;">Make a New Reservation</a>
        </div>
        
        <p>Questions? Contact us at {vars['restaurant_phone']} or {vars['restaurant_email']}</p>
        """
    
    def _generate_cancellation_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for reservation cancellation"""
        return f"""
        Reservation Cancellation
        
        Hi {vars['customer_name']},
        
        Your reservation has been cancelled by {vars['cancelled_by']}.
        
        CANCELLED RESERVATION DETAILS
        Date: {vars['reservation_date']}
        Time: {vars['reservation_time']}
        Party Size: {vars['party_size']} guests
        Confirmation Code: {vars['confirmation_code']}
        Reason: {vars['cancellation_reason']}
        
        We apologize for any inconvenience.
        
        Make a new reservation: {vars['rebooking_url']}
        
        Questions? Contact us at {vars['restaurant_phone']} or {vars['restaurant_email']}
        """
    
    def _generate_modification_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for reservation modification"""
        return f"""
        <h2>Your reservation has been updated</h2>
        <p>Hi {vars['customer_name']},</p>
        <p>Your reservation at {vars['restaurant_name']} has been successfully updated.</p>
        
        <div style="background-color: #d4edda; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Updated Reservation Details</h3>
            <p><strong>Date:</strong> {vars['reservation_date']}<br>
            <strong>Time:</strong> {vars['reservation_time']}<br>
            <strong>Party Size:</strong> {vars['party_size']} guests<br>
            <strong>Confirmation Code:</strong> {vars['confirmation_code']}</p>
            {% if special_requests %}
            <p><strong>Special Requests:</strong> {vars['special_requests']}</p>
            {% endif %}
        </div>
        
        <h3>Location</h3>
        <p>{vars['restaurant_name']}<br>
        {vars['restaurant_address']}<br>
        Phone: {vars['restaurant_phone']}</p>
        
        <p>We look forward to seeing you!</p>
        """
    
    def _generate_modification_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for reservation modification"""
        return f"""
        Your reservation has been updated
        
        Hi {vars['customer_name']},
        
        Your reservation at {vars['restaurant_name']} has been successfully updated.
        
        UPDATED RESERVATION DETAILS
        Date: {vars['reservation_date']}
        Time: {vars['reservation_time']}
        Party Size: {vars['party_size']} guests
        Confirmation Code: {vars['confirmation_code']}
        {f"Special Requests: {vars['special_requests']}" if vars.get('special_requests') else ""}
        
        LOCATION
        {vars['restaurant_name']}
        {vars['restaurant_address']}
        Phone: {vars['restaurant_phone']}
        
        We look forward to seeing you!
        """