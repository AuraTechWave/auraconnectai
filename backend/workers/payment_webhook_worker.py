#!/usr/bin/env python3
# backend/workers/payment_webhook_worker.py

"""
Payment Webhook Worker

Processes payment webhooks asynchronously using Arq.

Usage:
    python -m workers.payment_webhook_worker
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from arq import run_worker

from modules.payments.services.webhook_queue_service import get_worker_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run the payment webhook worker"""
    logger.info("Starting payment webhook worker...")
    
    try:
        # Run the worker
        asyncio.run(run_worker(get_worker_settings()))
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()