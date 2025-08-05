# backend/modules/staff/services/schedule_notification_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from ..models import Staff, Schedule
from core.config_validation import config as settings
# TODO: Fix import - notification service module structure changed
# from core.notifications import notification_service as core_notification
core_notification = None  # Temporary fix

logger = logging.getLogger(__name__)


class ScheduleNotificationService:
    """Service for handling schedule-related notifications"""
    
    def __init__(self):
        self.notification_channels = ["email", "sms", "push", "in_app"]
        self.batch_size = 50  # Send notifications in batches
    
    async def send_schedule_published_notifications(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        channels: List[str] = ["email", "in_app"],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notifications when schedule is published"""
        
        # Get all affected staff with their schedules
        affected_staff = await self._get_affected_staff(
            db, restaurant_id, start_date, end_date
        )
        
        if not affected_staff:
            return {
                "success": True,
                "total_staff": 0,
                "notifications_sent": {}
            }
        
        # Group notifications by channel
        results = {
            "success": True,
            "total_staff": len(affected_staff),
            "notifications_sent": {},
            "errors": []
        }
        
        # Send notifications through each channel
        for channel in channels:
            if channel in self.notification_channels:
                try:
                    sent_count = await self._send_by_channel(
                        channel, affected_staff, start_date, end_date, notes
                    )
                    results["notifications_sent"][channel] = sent_count
                except Exception as e:
                    logger.error(f"Error sending {channel} notifications: {e}")
                    results["errors"].append({
                        "channel": channel,
                        "error": str(e)
                    })
        
        return results
    
    async def send_schedule_updated_notifications(
        self,
        db: AsyncSession,
        restaurant_id: int,
        updated_schedules: List[Schedule],
        channels: List[str] = ["email", "push"]
    ) -> Dict[str, Any]:
        """Send notifications for schedule updates"""
        
        # Group schedules by staff
        staff_schedules = {}
        for schedule in updated_schedules:
            if schedule.staff_id not in staff_schedules:
                staff_schedules[schedule.staff_id] = []
            staff_schedules[schedule.staff_id].append(schedule)
        
        # Get staff details
        staff_ids = list(staff_schedules.keys())
        staff_result = await db.execute(
            select(Staff).where(
                and_(
                    Staff.restaurant_id == restaurant_id,
                    Staff.id.in_(staff_ids),
                    Staff.is_active == True
                )
            )
        )
        staff_list = staff_result.scalars().all()
        
        # Prepare notification data
        notification_data = []
        for staff in staff_list:
            schedules = staff_schedules.get(staff.id, [])
            if schedules:
                notification_data.append({
                    "staff": staff,
                    "updated_schedules": schedules
                })
        
        # Send notifications
        results = {
            "success": True,
            "total_staff": len(notification_data),
            "notifications_sent": {}
        }
        
        for channel in channels:
            if channel in self.notification_channels:
                try:
                    sent_count = await self._send_update_notifications(
                        channel, notification_data
                    )
                    results["notifications_sent"][channel] = sent_count
                except Exception as e:
                    logger.error(f"Error sending {channel} update notifications: {e}")
        
        return results
    
    async def send_shift_reminders(
        self,
        db: AsyncSession,
        restaurant_id: int,
        hours_before: int = 2
    ) -> Dict[str, Any]:
        """Send reminders for upcoming shifts"""
        
        # Calculate reminder window
        now = datetime.utcnow()
        reminder_start = now + timedelta(hours=hours_before - 0.5)
        reminder_end = now + timedelta(hours=hours_before + 0.5)
        
        # Get upcoming shifts in reminder window
        query = select(Schedule).where(
            and_(
                Schedule.restaurant_id == restaurant_id,
                Schedule.date >= now.date(),
                Schedule.is_published == True,
                Schedule.reminder_sent == False
            )
        ).options(selectinload(Schedule.staff))
        
        result = await db.execute(query)
        upcoming_shifts = result.scalars().all()
        
        # Filter shifts in reminder window
        shifts_to_remind = []
        for shift in upcoming_shifts:
            shift_start = datetime.combine(shift.date, shift.start_time)
            if reminder_start <= shift_start <= reminder_end:
                shifts_to_remind.append(shift)
        
        if not shifts_to_remind:
            return {
                "success": True,
                "reminders_sent": 0
            }
        
        # Send reminders
        sent_count = 0
        errors = []
        
        for shift in shifts_to_remind:
            try:
                await self._send_shift_reminder(shift)
                shift.reminder_sent = True
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending reminder for shift {shift.id}: {e}")
                errors.append({
                    "shift_id": shift.id,
                    "staff_name": shift.staff.name,
                    "error": str(e)
                })
        
        await db.commit()
        
        return {
            "success": len(errors) == 0,
            "reminders_sent": sent_count,
            "errors": errors
        }
    
    async def _get_affected_staff(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get staff affected by schedule publication"""
        
        # Get all schedules in date range with staff details
        query = select(Schedule).where(
            and_(
                Schedule.restaurant_id == restaurant_id,
                Schedule.date >= start_date,
                Schedule.date <= end_date,
                Schedule.is_published == True
            )
        ).options(selectinload(Schedule.staff))
        
        result = await db.execute(query)
        schedules = result.scalars().all()
        
        # Group by staff
        staff_data = {}
        for schedule in schedules:
            if schedule.staff_id not in staff_data:
                staff_data[schedule.staff_id] = {
                    "staff": schedule.staff,
                    "schedules": []
                }
            staff_data[schedule.staff_id]["schedules"].append(schedule)
        
        return list(staff_data.values())
    
    async def _send_by_channel(
        self,
        channel: str,
        staff_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        notes: Optional[str] = None
    ) -> int:
        """Send notifications through specific channel"""
        
        if channel == "email":
            return await self._send_email_notifications(
                staff_data, start_date, end_date, notes
            )
        elif channel == "sms":
            return await self._send_sms_notifications(
                staff_data, start_date, end_date
            )
        elif channel == "push":
            return await self._send_push_notifications(
                staff_data, start_date, end_date
            )
        elif channel == "in_app":
            return await self._send_in_app_notifications(
                staff_data, start_date, end_date, notes
            )
        
        return 0
    
    async def _send_email_notifications(
        self,
        staff_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        notes: Optional[str] = None
    ) -> int:
        """Send email notifications in batches"""
        
        sent_count = 0
        
        # Process in batches
        for i in range(0, len(staff_data), self.batch_size):
            batch = staff_data[i:i + self.batch_size]
            
            # Prepare batch emails
            email_tasks = []
            for item in batch:
                staff = item["staff"]
                if staff.email:
                    email_content = self._create_schedule_email(
                        staff, item["schedules"], start_date, end_date, notes
                    )
                    email_tasks.append(
                        core_notification.send_email(
                            to=staff.email,
                            subject=f"Your Schedule for {start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}",
                            html_content=email_content
                        )
                    )
            
            # Send batch
            if email_tasks:
                results = await asyncio.gather(*email_tasks, return_exceptions=True)
                sent_count += sum(1 for r in results if not isinstance(r, Exception))
        
        return sent_count
    
    def _create_schedule_email(
        self,
        staff: Staff,
        schedules: List[Schedule],
        start_date: date,
        end_date: date,
        notes: Optional[str] = None
    ) -> str:
        """Create HTML email content for schedule notification"""
        
        # Sort schedules by date
        schedules.sort(key=lambda s: s.date)
        
        schedule_html = ""
        for schedule in schedules:
            schedule_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    {schedule.date.strftime('%A, %B %d')}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    {schedule.start_time.strftime('%I:%M %p')} - {schedule.end_time.strftime('%I:%M %p')}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    {schedule.total_hours} hours
                </td>
            </tr>
            """
        
        notes_section = ""
        if notes:
            notes_section = f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px;">
                <h3 style="margin-top: 0;">Manager's Notes:</h3>
                <p>{notes}</p>
            </div>
            """
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #333;">Hi {staff.name},</h2>
                    
                    <p>Your schedule for <strong>{start_date.strftime('%B %d')} - {end_date.strftime('%B %d')}</strong> has been published.</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="padding: 10px; text-align: left;">Date</th>
                                <th style="padding: 10px; text-align: left;">Shift Time</th>
                                <th style="padding: 10px; text-align: left;">Duration</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html}
                        </tbody>
                    </table>
                    
                    <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px;">
                        <strong>Total Hours This Week:</strong> {sum(s.total_hours for s in schedules)} hours
                    </div>
                    
                    {notes_section}
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 14px;">
                        <p>If you have any questions about your schedule, please contact your manager.</p>
                        <p>You can also view your schedule in the staff app.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    async def _send_sms_notifications(
        self,
        staff_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date
    ) -> int:
        """Send SMS notifications"""
        
        sent_count = 0
        
        for item in staff_data:
            staff = item["staff"]
            if staff.phone:
                # Calculate total hours
                total_hours = sum(s.total_hours for s in item["schedules"])
                
                message = (
                    f"Hi {staff.name}, your schedule for "
                    f"{start_date.strftime('%b %d')}-{end_date.strftime('%b %d')} "
                    f"is ready. Total: {total_hours} hours. "
                    f"Check the app for details."
                )
                
                try:
                    await core_notification.send_sms(staff.phone, message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"SMS failed for {staff.name}: {e}")
        
        return sent_count
    
    async def _send_push_notifications(
        self,
        staff_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date
    ) -> int:
        """Send push notifications"""
        
        sent_count = 0
        
        for item in staff_data:
            staff = item["staff"]
            
            # Get device tokens for staff
            device_tokens = await core_notification.get_device_tokens(staff.id)
            
            if device_tokens:
                title = "Schedule Published"
                body = (
                    f"Your schedule for {start_date.strftime('%b %d')}-"
                    f"{end_date.strftime('%b %d')} is now available"
                )
                
                data = {
                    "type": "schedule_published",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
                
                try:
                    await core_notification.send_push(
                        device_tokens, title, body, data
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Push notification failed for {staff.name}: {e}")
        
        return sent_count
    
    async def _send_in_app_notifications(
        self,
        staff_data: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        notes: Optional[str] = None
    ) -> int:
        """Create in-app notifications"""
        
        sent_count = 0
        
        for item in staff_data:
            staff = item["staff"]
            
            notification_data = {
                "user_id": staff.id,
                "type": "schedule_published",
                "title": "Schedule Published",
                "message": (
                    f"Your schedule for {start_date.strftime('%b %d')}-"
                    f"{end_date.strftime('%b %d')} has been published. "
                    f"You have {len(item['schedules'])} shifts scheduled."
                ),
                "data": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "shift_count": len(item["schedules"]),
                    "total_hours": sum(s.total_hours for s in item["schedules"]),
                    "notes": notes
                }
            }
            
            try:
                await core_notification.create_in_app_notification(notification_data)
                sent_count += 1
            except Exception as e:
                logger.error(f"In-app notification failed for {staff.name}: {e}")
        
        return sent_count
    
    async def _send_update_notifications(
        self,
        channel: str,
        notification_data: List[Dict[str, Any]]
    ) -> int:
        """Send update notifications through specific channel"""
        
        # Similar implementation to published notifications
        # but with different message templates
        sent_count = 0
        
        for item in notification_data:
            staff = item["staff"]
            schedules = item["updated_schedules"]
            
            if channel == "email" and staff.email:
                subject = "Schedule Update"
                body = self._create_update_email(staff, schedules)
                
                try:
                    await core_notification.send_email(
                        staff.email, subject, body
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Update email failed for {staff.name}: {e}")
            
            elif channel == "push":
                device_tokens = await core_notification.get_device_tokens(staff.id)
                if device_tokens:
                    title = "Schedule Updated"
                    body = f"Your schedule has been updated. {len(schedules)} shifts affected."
                    
                    try:
                        await core_notification.send_push(
                            device_tokens, title, body,
                            {"type": "schedule_updated", "shift_count": len(schedules)}
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Update push failed for {staff.name}: {e}")
        
        return sent_count
    
    def _create_update_email(self, staff: Staff, schedules: List[Schedule]) -> str:
        """Create email content for schedule updates"""
        
        changes_html = ""
        for schedule in schedules:
            changes_html += f"""
            <li style="margin-bottom: 10px;">
                <strong>{schedule.date.strftime('%A, %B %d')}:</strong> 
                {schedule.start_time.strftime('%I:%M %p')} - {schedule.end_time.strftime('%I:%M %p')}
            </li>
            """
        
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <h2>Schedule Update</h2>
                    <p>Hi {staff.name},</p>
                    <p>Your schedule has been updated. The following shifts have been changed:</p>
                    <ul>
                        {changes_html}
                    </ul>
                    <p>Please check the staff app for full details.</p>
                </div>
            </body>
        </html>
        """
    
    async def _send_shift_reminder(self, shift: Schedule):
        """Send reminder for a single shift"""
        
        staff = shift.staff
        shift_start = datetime.combine(shift.date, shift.start_time)
        
        # Send push notification if available
        device_tokens = await core_notification.get_device_tokens(staff.id)
        if device_tokens:
            title = "Shift Reminder"
            body = f"Your shift starts at {shift.start_time.strftime('%I:%M %p')} today"
            
            await core_notification.send_push(
                device_tokens, title, body,
                {"type": "shift_reminder", "shift_id": shift.id}
            )
        
        # Send SMS if configured
        if staff.phone and staff.notification_preferences.get("sms_reminders", False):
            message = (
                f"Reminder: Your shift starts at "
                f"{shift.start_time.strftime('%I:%M %p')} today. "
                f"Don't forget to clock in!"
            )
            await core_notification.send_sms(staff.phone, message)


# Create singleton service
schedule_notification_service = ScheduleNotificationService()