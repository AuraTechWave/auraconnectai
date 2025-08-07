# backend/modules/reservations/services/notification_service.py

"""
Notification service for reservation confirmations, reminders, and updates.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date, time
from typing import Optional, Dict, Any
import logging
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..models.reservation_models import (
    Reservation, Waitlist, NotificationMethod, ReservationStatus
)
from core.config import settings
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class ReservationNotificationService:
    """Service for handling reservation-related notifications"""
    
    def __init__(self, db: Session):
        self.db = db
        # These would be initialized with actual email/SMS services
        self.email_service = None  # EmailService()
        self.sms_service = None    # SMSService()
    
    async def send_booking_confirmation(self, reservation: Reservation):
        """Send initial booking confirmation"""
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            logger.error(f"Customer {reservation.customer_id} not found for reservation {reservation.id}")
            return
        
        # Prepare notification data
        notification_data = {
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "reservation_date": reservation.reservation_date.strftime("%B %d, %Y"),
            "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
            "party_size": reservation.party_size,
            "confirmation_code": reservation.confirmation_code,
            "table_numbers": reservation.table_numbers,
            "special_requests": reservation.special_requests,
            "restaurant_name": "AuraConnect Restaurant",
            "restaurant_phone": settings.RESTAURANT_PHONE,
            "restaurant_address": settings.RESTAURANT_ADDRESS
        }
        
        # Send based on notification preference
        if reservation.notification_method in [NotificationMethod.EMAIL, NotificationMethod.BOTH]:
            await self._send_email_confirmation(customer.email, notification_data)
        
        if reservation.notification_method in [NotificationMethod.SMS, NotificationMethod.BOTH]:
            if customer.phone:
                await self._send_sms_confirmation(customer.phone, notification_data)
        
        logger.info(f"Sent booking confirmation for reservation {reservation.id}")
    
    async def _send_email_confirmation(self, email: str, data: Dict[str, Any]):
        """Send email confirmation"""
        subject = f"Reservation Confirmed - {data['confirmation_code']}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Reservation Confirmed!</h2>
                    
                    <p>Dear {data['customer_name']},</p>
                    
                    <p>Your reservation has been confirmed. Here are your details:</p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Confirmation Code:</strong> {data['confirmation_code']}</p>
                        <p><strong>Date:</strong> {data['reservation_date']}</p>
                        <p><strong>Time:</strong> {data['reservation_time']}</p>
                        <p><strong>Party Size:</strong> {data['party_size']} guests</p>
                        {f"<p><strong>Table:</strong> {data['table_numbers']}</p>" if data['table_numbers'] else ""}
                        {f"<p><strong>Special Requests:</strong> {data['special_requests']}</p>" if data['special_requests'] else ""}
                    </div>
                    
                    <p><strong>Restaurant Details:</strong></p>
                    <p>{data['restaurant_name']}<br>
                    {data['restaurant_address']}<br>
                    Phone: {data['restaurant_phone']}</p>
                    
                    <p style="margin-top: 30px;">
                        <a href="#" style="background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Manage Reservation
                        </a>
                    </p>
                    
                    <p style="font-size: 12px; color: #7f8c8d; margin-top: 30px;">
                        If you need to cancel or modify your reservation, please do so at least 2 hours in advance.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # In production, this would use actual email service
        logger.info(f"Would send email to {email}: {subject}")
        # await self.email_service.send(email, subject, html_body)
    
    async def _send_sms_confirmation(self, phone: str, data: Dict[str, Any]):
        """Send SMS confirmation"""
        message = f"""
{data['restaurant_name']} Reservation Confirmed!
Code: {data['confirmation_code']}
Date: {data['reservation_date']}
Time: {data['reservation_time']}
Party: {data['party_size']} guests
Reply CANCEL to cancel.
        """.strip()
        
        # In production, this would use actual SMS service
        logger.info(f"Would send SMS to {phone}: {message}")
        # await self.sms_service.send(phone, message)
    
    async def send_reminder(self, reservation: Reservation):
        """Send reservation reminder"""
        if reservation.reminder_sent:
            logger.info(f"Reminder already sent for reservation {reservation.id}")
            return
        
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            return
        
        notification_data = {
            "customer_name": f"{customer.first_name}",
            "reservation_date": reservation.reservation_date.strftime("%B %d, %Y"),
            "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
            "party_size": reservation.party_size,
            "confirmation_code": reservation.confirmation_code,
            "hours_until": 24  # Typically sent 24 hours before
        }
        
        if reservation.notification_method in [NotificationMethod.EMAIL, NotificationMethod.BOTH]:
            await self._send_email_reminder(customer.email, notification_data)
        
        if reservation.notification_method in [NotificationMethod.SMS, NotificationMethod.BOTH]:
            if customer.phone:
                await self._send_sms_reminder(customer.phone, notification_data)
        
        # Mark reminder as sent
        reservation.reminder_sent = True
        reservation.reminder_sent_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Sent reminder for reservation {reservation.id}")
    
    async def _send_email_reminder(self, email: str, data: Dict[str, Any]):
        """Send email reminder"""
        subject = f"Reservation Reminder - Tomorrow at {data['reservation_time']}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Reservation Reminder</h2>
                    
                    <p>Hi {data['customer_name']},</p>
                    
                    <p>This is a friendly reminder about your reservation tomorrow:</p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Date:</strong> {data['reservation_date']}</p>
                        <p><strong>Time:</strong> {data['reservation_time']}</p>
                        <p><strong>Party Size:</strong> {data['party_size']} guests</p>
                        <p><strong>Confirmation Code:</strong> {data['confirmation_code']}</p>
                    </div>
                    
                    <p>We look forward to seeing you!</p>
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        Need to make changes? Please call us or manage your reservation online.
                    </p>
                </div>
            </body>
        </html>
        """
        
        logger.info(f"Would send reminder email to {email}")
    
    async def _send_sms_reminder(self, phone: str, data: Dict[str, Any]):
        """Send SMS reminder"""
        message = f"""
Reminder: Your reservation is tomorrow at {data['reservation_time']}.
Party of {data['party_size']}.
Code: {data['confirmation_code']}
See you soon!
        """.strip()
        
        logger.info(f"Would send reminder SMS to {phone}")
    
    async def send_update_notification(self, reservation: Reservation):
        """Send notification when reservation is updated"""
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            return
        
        subject = "Reservation Updated"
        message = f"Your reservation {reservation.confirmation_code} has been updated."
        
        # Send notification based on preference
        logger.info(f"Sent update notification for reservation {reservation.id}")
    
    async def send_cancellation_notification(self, reservation: Reservation, reason: Optional[str]):
        """Send cancellation confirmation"""
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            return
        
        notification_data = {
            "customer_name": f"{customer.first_name}",
            "confirmation_code": reservation.confirmation_code,
            "reservation_date": reservation.reservation_date.strftime("%B %d, %Y"),
            "reservation_time": reservation.reservation_time.strftime("%I:%M %p"),
            "reason": reason or "No reason provided"
        }
        
        if reservation.notification_method in [NotificationMethod.EMAIL, NotificationMethod.BOTH]:
            await self._send_cancellation_email(customer.email, notification_data)
        
        if reservation.notification_method in [NotificationMethod.SMS, NotificationMethod.BOTH]:
            if customer.phone:
                await self._send_cancellation_sms(customer.phone, notification_data)
        
        logger.info(f"Sent cancellation notification for reservation {reservation.id}")
    
    async def _send_cancellation_email(self, email: str, data: Dict[str, Any]):
        """Send cancellation email"""
        subject = f"Reservation Cancelled - {data['confirmation_code']}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #e74c3c;">Reservation Cancelled</h2>
                    
                    <p>Hi {data['customer_name']},</p>
                    
                    <p>Your reservation has been cancelled:</p>
                    
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Confirmation Code:</strong> {data['confirmation_code']}</p>
                        <p><strong>Original Date:</strong> {data['reservation_date']}</p>
                        <p><strong>Original Time:</strong> {data['reservation_time']}</p>
                        <p><strong>Reason:</strong> {data['reason']}</p>
                    </div>
                    
                    <p>We hope to see you again soon!</p>
                    
                    <p style="margin-top: 30px;">
                        <a href="#" style="background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Make a New Reservation
                        </a>
                    </p>
                </div>
            </body>
        </html>
        """
        
        logger.info(f"Would send cancellation email to {email}")
    
    async def _send_cancellation_sms(self, phone: str, data: Dict[str, Any]):
        """Send cancellation SMS"""
        message = f"""
Your reservation {data['confirmation_code']} for {data['reservation_date']} at {data['reservation_time']} has been cancelled.
        """.strip()
        
        logger.info(f"Would send cancellation SMS to {phone}")
    
    async def send_confirmation_status_notification(self, reservation: Reservation):
        """Send notification when reservation is confirmed by staff"""
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            return
        
        subject = "Reservation Confirmed by Restaurant"
        message = f"Your reservation {reservation.confirmation_code} has been confirmed by our staff."
        
        logger.info(f"Sent confirmation status notification for reservation {reservation.id}")
    
    # Waitlist notifications
    async def send_waitlist_confirmation(self, waitlist_entry: Waitlist):
        """Send waitlist confirmation"""
        customer = self.db.query(Customer).filter_by(id=waitlist_entry.customer_id).first()
        if not customer:
            return
        
        notification_data = {
            "customer_name": f"{customer.first_name}",
            "requested_date": waitlist_entry.requested_date.strftime("%B %d, %Y"),
            "requested_time": f"{waitlist_entry.requested_time_start.strftime('%I:%M %p')} - {waitlist_entry.requested_time_end.strftime('%I:%M %p')}",
            "party_size": waitlist_entry.party_size,
            "position": waitlist_entry.position
        }
        
        subject = "Added to Waitlist"
        message = f"You're #{waitlist_entry.position} on the waitlist for {notification_data['requested_date']}"
        
        logger.info(f"Sent waitlist confirmation for entry {waitlist_entry.id}")
    
    async def send_waitlist_availability_notification(
        self,
        waitlist_entry: Waitlist,
        available_date: date,
        available_time: time,
        response_window_minutes: int
    ):
        """Send notification when table becomes available from waitlist"""
        customer = self.db.query(Customer).filter_by(id=waitlist_entry.customer_id).first()
        if not customer:
            return
        
        notification_data = {
            "customer_name": f"{customer.first_name}",
            "available_date": available_date.strftime("%B %d, %Y"),
            "available_time": available_time.strftime("%I:%M %p"),
            "party_size": waitlist_entry.party_size,
            "response_minutes": response_window_minutes,
            "confirmation_link": f"{settings.FRONTEND_URL}/waitlist/confirm/{waitlist_entry.id}"
        }
        
        # For waitlist availability, prefer SMS for urgency
        if waitlist_entry.notification_method in [NotificationMethod.SMS, NotificationMethod.BOTH]:
            if customer.phone:
                await self._send_waitlist_availability_sms(customer.phone, notification_data)
        
        if waitlist_entry.notification_method in [NotificationMethod.EMAIL, NotificationMethod.BOTH]:
            await self._send_waitlist_availability_email(customer.email, notification_data)
        
        logger.info(f"Sent waitlist availability notification for entry {waitlist_entry.id}")
    
    async def _send_waitlist_availability_sms(self, phone: str, data: Dict[str, Any]):
        """Send urgent SMS for waitlist availability"""
        message = f"""
Table available NOW!
{data['available_date']} at {data['available_time']}
Party of {data['party_size']}
Reply YES within {data['response_minutes']} min to confirm.
        """.strip()
        
        logger.info(f"Would send waitlist SMS to {phone}")
    
    async def _send_waitlist_availability_email(self, email: str, data: Dict[str, Any]):
        """Send email for waitlist availability"""
        subject = "🎉 Table Available - Act Fast!"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #27ae60;">A Table Just Became Available!</h2>
                    
                    <p>Hi {data['customer_name']},</p>
                    
                    <p><strong>Great news!</strong> A table matching your request is now available:</p>
                    
                    <div style="background-color: #e8f5e9; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Date:</strong> {data['available_date']}</p>
                        <p><strong>Time:</strong> {data['available_time']}</p>
                        <p><strong>Party Size:</strong> {data['party_size']} guests</p>
                    </div>
                    
                    <p style="color: #e74c3c;"><strong>⏰ You have {data['response_minutes']} minutes to confirm!</strong></p>
                    
                    <p style="margin: 30px 0;">
                        <a href="{data['confirmation_link']}" style="background-color: #27ae60; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 18px;">
                            Confirm Reservation Now
                        </a>
                    </p>
                    
                    <p style="font-size: 12px; color: #7f8c8d;">
                        This offer will expire if not confirmed within {data['response_minutes']} minutes.
                    </p>
                </div>
            </body>
        </html>
        """
        
        logger.info(f"Would send waitlist availability email to {email}")
    
    async def send_confirmation_reminder(self, reservation: Reservation):
        """Send reminder to confirm reservation"""
        customer = self.db.query(Customer).filter_by(id=reservation.customer_id).first()
        if not customer:
            return
        
        subject = "Please Confirm Your Reservation"
        message = f"Please confirm your reservation {reservation.confirmation_code} for {reservation.reservation_date}"
        
        logger.info(f"Sent confirmation reminder for reservation {reservation.id}")
    
    async def schedule_reminder(self, reservation: Reservation, hours_before: int):
        """Schedule a reminder to be sent later"""
        # Calculate when to send reminder
        reminder_time = datetime.combine(
            reservation.reservation_date,
            reservation.reservation_time
        ) - timedelta(hours=hours_before)
        
        # In production, this would use a task scheduler like Celery or APScheduler
        # For now, we'll create a scheduled task entry
        from ..models.reservation_models import ScheduledReminder
        
        reminder = ScheduledReminder(
            reservation_id=reservation.id,
            scheduled_for=reminder_time,
            reminder_type="reservation_reminder",
            status="pending"
        )
        self.db.add(reminder)
        self.db.commit()
        
        logger.info(f"Scheduled reminder for reservation {reservation.id} at {reminder_time}")
        # In production: await task_scheduler.schedule(self.send_reminder, reservation.id, run_at=reminder_time)
    
    async def process_scheduled_reminders(self):
        """Process all due scheduled reminders"""
        from ..models.reservation_models import ScheduledReminder
        
        # Find due reminders
        now = datetime.utcnow()
        due_reminders = self.db.query(ScheduledReminder).filter(
            ScheduledReminder.scheduled_for <= now,
            ScheduledReminder.status == "pending"
        ).all()
        
        for reminder in due_reminders:
            try:
                # Get reservation
                reservation = self.db.query(Reservation).filter_by(
                    id=reminder.reservation_id
                ).first()
                
                if reservation and reservation.status in [
                    ReservationStatus.PENDING,
                    ReservationStatus.CONFIRMED
                ]:
                    await self.send_reminder(reservation)
                    reminder.status = "sent"
                    reminder.sent_at = now
                else:
                    reminder.status = "skipped"
                    reminder.extra_data = {"reason": "Reservation not eligible"}
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {str(e)}")
                reminder.status = "failed"
                reminder.extra_data = {"error": str(e)}
            
            self.db.commit()