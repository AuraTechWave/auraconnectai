# backend/modules/reservations/tasks/reminder_tasks.py

"""
Background task for processing scheduled reminders.
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from core.database import SessionLocal
from ..services.notification_service import ReservationNotificationService

logger = logging.getLogger(__name__)


async def process_scheduled_reminders():
    """
    Process all due scheduled reminders.
    This should be run periodically (e.g., every 5 minutes) by a scheduler.
    """
    db = SessionLocal()
    try:
        notification_service = ReservationNotificationService(db)
        await notification_service.process_scheduled_reminders()
        logger.info("Processed scheduled reminders")
    except Exception as e:
        logger.error(f"Error processing scheduled reminders: {str(e)}")
    finally:
        db.close()


async def run_reminder_scheduler():
    """
    Run the reminder scheduler continuously.
    This can be started as a background task when the application starts.
    """
    logger.info("Starting reminder scheduler")
    
    while True:
        try:
            await process_scheduled_reminders()
        except Exception as e:
            logger.error(f"Error in reminder scheduler: {str(e)}")
        
        # Wait 5 minutes before next check
        await asyncio.sleep(300)


# Example of how to integrate with FastAPI startup:
# 
# from fastapi import FastAPI
# import asyncio
# 
# app = FastAPI()
# 
# @app.on_event("startup")
# async def startup_event():
#     # Start the reminder scheduler as a background task
#     asyncio.create_task(run_reminder_scheduler())