import asyncio
import logging
import threading
from typing import Optional

from .deltasleeper import AioDeltaSleeper
from .other import run_callable

logger = logging.getLogger(__name__)


class AioDeltaCountdown:
    def __init__(self, seconds=None):
        self.__seconds = seconds
        self._sleeper: AioDeltaSleeper = AioDeltaSleeper()
        self._cancelled = False
        self._paused = False
        self.SpecifiedTimeAlreadyPassed = self._sleeper.SpecifiedTimeAlreadyPassed

    class Cancelled(Exception):
        pass

    class Paused(Exception):
        pass

    async def wait_count(self, seconds):
        if self._cancelled:
            raise self.Cancelled
        elif self._paused:
            logger.info("Tried to wait although timer got paused.")
            raise self.Paused
        else:
            await self._sleeper(seconds)
            self.seconds -= seconds

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._cancelled = True

    @property
    def seconds(self):
        return self.__seconds

    @seconds.setter
    def seconds(self, val):
        if val < 0:
            raise ValueError(f"The amount of seconds must be bigger than 0, but {val} was given.")
        self.__seconds = val

    def pause(self):
        self._paused = True

    @property
    def is_paused(self):
        return self._paused

    def resume(self):
        self._sleeper.set_current_time()
        self._paused = False

    def cancel(self):
        self._cancelled = True


class DeltaCountdownTask(AioDeltaCountdown):
    def __init__(self, seconds=None, callback_on_zero=None, callback_every_second=None):
        super().__init__(seconds)
        self.callback_on_zero = callback_on_zero  # When sec == 0 without cancel, runs callback() or await callback().
        self.callback_every_second = callback_every_second  # Runs every second.
        self._task: Optional[asyncio.Task] = None

    def is_running(self):
        return self._task and not self._task.cancelled()

    def run_count_task(self):
        if not self.is_running:
            self._task = asyncio.create_task(self.count_task_main())
            return self._task

    async def count_task_main(self):
        logger.debug(f"{self.__class__.__name__} started countdown")
        with threading.Lock():
            while self.__seconds:
                try:
                    await self._sleeper(1)
                except asyncio.CancelledError:
                    logger.debug(f"{self.__class__.__name__} cancelled countdown")
                    raise
                else:
                    await run_callable(self.callback_every_second)
                finally:
                    self.seconds -= 1
            else:
                await run_callable(self.callback_on_zero)

    def cancel(self):
        if self._task and not self._task.cancelled():
            self._task.cancel()
            self._task = None

    def pause(self):
        self.cancel()

    def resume(self):
        self.run_count_task()
