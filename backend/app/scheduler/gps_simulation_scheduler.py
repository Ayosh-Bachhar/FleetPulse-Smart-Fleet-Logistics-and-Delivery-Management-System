import asyncio
import logging

from app.services.simulated_gps_service import (
    GPS_INTERVAL_SECONDS,
    tick_running_simulations,
)


logger = logging.getLogger(__name__)


async def gps_simulation_loop():
    """
    F14 backend scheduler.

    Runs independently of React/browser requests.
    It advances running simulations every 5 seconds.
    """
    while True:
        await asyncio.sleep(GPS_INTERVAL_SECONDS)

        try:
            await tick_running_simulations()

        except Exception:
            logger.exception(
                "F14 GPS scheduler encountered an error."
            )