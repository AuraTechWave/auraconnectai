# backend/modules/tables/services/startup_service.py

"""
Table management startup and shutdown services
"""

import logging
from .realtime_table_service import realtime_table_service

logger = logging.getLogger(__name__)


async def start_table_services():
    """Start all table-related background services"""
    try:
        # Start real-time monitoring
        await realtime_table_service.start_monitoring()
        logger.info("Table real-time services started successfully")
    except Exception as e:
        logger.error(f"Failed to start table services: {e}")
        raise


async def stop_table_services():
    """Stop all table-related background services"""
    try:
        # Stop real-time monitoring
        await realtime_table_service.stop_monitoring()
        logger.info("Table real-time services stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop table services: {e}")
        # Don't raise on shutdown errors