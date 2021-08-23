import logging
from typing import Union, Optional
import asyncio
import threading
from inspect import iscoroutinefunction
import datetime
from .run_callable import run_callable


logger = logging.getLogger(__name__)


now = datetime.datetime.now
sleep = asyncio.sleep
number = Union[int, float]


class AioDeltaSleeper:
    """ Sleeps for requested seconds compared with last time.
    e.g.
    sleeper = AioDeltaSleeper()
    while True:
        await asyncio.sleep(2)
        await sleeper.sleep(5)

    In this case, sleeper.sleep(5) just sleeps around 3 seconds every time. 3 was calculated by 5 - 2.
    Useful class when you wanna run async function at regular intervals with unstable function.
    """
    def __init__(self, callback: callable = None, precision=0.001, multiplier=0.9) -> None:
        if precision < 0:
            raise ValueError(f"Precision must be bigger than 0, but {precision} was given.")
        if multiplier > 1:
            raise ValueError(f"Multiplier for sleep time cannot be bigger than 0, but {multiplier} was given.")
        self._multiplier_for_sleep_time = multiplier
        self._precision: float = precision
        self._callback = callback
        self._callback_task = None
        self._callback_result = None
        self._last_time: datetime.datetime = now()

    class SpecifiedTimeAlreadyPassed(Exception):
        pass

    async def sleep(self, requested_sec: number) -> None:
        sleep_time: number = self._calculate_sleep_time(requested_sec)
        if sleep_time < 0:
            error_message = f"Calculated sleep time:{sleep_time} was less than 0."
            logger.warning(error_message)
            self._last_time += datetime.timedelta(seconds=requested_sec)
            raise self.SpecifiedTimeAlreadyPassed(error_message)
        while sleep_time > requested_sec*self._precision:
            sleep_time = self._calculate_sleep_time(requested_sec)
            await sleep(sleep_time * self._multiplier_for_sleep_time)
        if self._callback:
            if iscoroutinefunction(self._callback):
                self._callback_task = asyncio.create_task(self._callback())
            else:
                self._callback_result = self._callback()
        self._last_time += datetime.timedelta(seconds=requested_sec)

    def _calculate_sleep_time(self, requested_sec: number) -> number:
        time_delta: datetime.timedelta = now() - self._last_time
        delta_seconds = time_delta.seconds + time_delta.microseconds / 1000000
        return float(requested_sec) - delta_seconds

    async def __call__(self, requested_sec: number) -> None:
        await self.sleep(requested_sec)

    async def set_current_time(self):
        self._last_time = now()


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


class CountdownAsTask(AioDeltaCountdown):
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