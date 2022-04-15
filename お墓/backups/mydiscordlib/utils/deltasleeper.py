import asyncio
import datetime
import logging
from inspect import iscoroutinefunction
from typing import Union

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
        while sleep_time > requested_sec * self._precision:
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
