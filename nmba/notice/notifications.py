import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

import apprise

_apprise_instance = None
_apprise_lock = threading.Lock()

def get_apprise_instance():
    """Get or create the singleton Apprise instance."""
    global _apprise_instance
    with _apprise_lock:
        if _apprise_instance is None:
            _apprise_instance = apprise.Apprise()
            services_added = False
            for key, value in os.environ.items():
                if key.startswith("APPRISE_"):
                    logger.info(f"Adding notification service: {key}")
                    _apprise_instance.add(value)
                    services_added = True
            if not services_added:
                logger.warning("No notification services configured in environment variables")
        return _apprise_instance

async def send_notification_async(message: str, title: str = "Bill Reminder") -> None:
    """Send notification asynchronously using Apprise with environment variables."""
    def notify_sync():
        try:
            apobj = get_apprise_instance()
            if not apobj.servers:
                logger.warning("No notification services available, skipping notification")
                return
            logger.info("Sending notification")
            success = apobj.notify(body=message, title=title)
            if success:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification")
        except Exception as e:
            logger.exception(f"Error sending notification: {e}")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(ThreadPoolExecutor(), notify_sync)
