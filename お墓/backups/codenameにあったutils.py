import asyncio
import datetime
import inspect
import logging
import threading
from collections.abc import Callable
from typing import Optional, Union

num_emojis = ['0⃣', '1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣', '9⃣']
num_zenkakus = ['０', '１', '２', '３', '４', '５', '６', '７', '８', '９']
num_kanjis = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']

for_std_num_trans = str.maketrans("".join([char1 + char2 for char1, char2 in zip(num_zenkakus, num_kanjis)]),
                                  "".join([str(i) + str(i) for i in range(10)]))

logger = logging.getLogger(__name__)


class AioCountdown:
    def __init__(self, seconds=None, callback=None, loop_sleep_sec=0.1):
        self.__seconds = seconds
        self._callback = callback  # callback() or await callback() happens when sec == 0 without cancel
        self._task: Optional[asyncio.Task] = None
        self._loop_sleep_sec = loop_sleep_sec

    def start(self):
        if not self.is_running:
            self._task = asyncio.create_task(self.count())

    async def count(self):
        logger.debug(f"{self.__class__.__name__} started countdown")
        with threading.Lock():
            while self.__seconds:
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    logger.debug(f"{self.__class__.__name__} cancelld countdown")
                    raise asyncio.CancelledError
                else:
                    self.__seconds -= 1
            else:
                if inspect.iscoroutinefunction(self._callback):
                    await self._callback()
                else:
                    self._callback()

    def cancel(self):
        if self._task and not self._task.cancelled():
            self._task.cancel()
            self._task = None

    def resume(self):
        self.start()

    @property
    def seconds(self):
        return self.__seconds

    @property
    def is_running(self):
        return self._task
        # Detect by if bool(self._task.cancelled()) sometimes doesn't work since cancelling might take a few seconds.
        # Therefore, this code detects if is_running or not by checking task attribute directly.

    @property
    def is_paused(self):
        return not self.is_running and self.__seconds

    def set_callback(self, callback: Callable):
        self._callback = callback

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel()


class AioDeltaSleeper:
    now = datetime.datetime.now
    sleep = asyncio.sleep

    def __init__(self):
        self._last_time: datetime.datetime = datetime.datetime.now()

    async def wait(self, requested_sec: Union[int, float]) -> None:
        # noinspection PyTypeChecker
        current_time: datetime.datetime = self.now()
        delta: datetime.timedelta = current_time - self._last_time
        sleep_time: float = float(requested_sec) - delta.microseconds / 1000000
        if sleep_time > 1:
            await self.sleep(delta.seconds - 1)
        while True:
            sleep_time: float = float(requested_sec) - delta.microseconds / 1000000
            if sleep_time < 0:
                logger.warning(f"Calculated sleep time:{sleep_time} was less than 0."
                               f"Maybe some processes before sleep took longer time than expected or "
                               f"requested seconds to sleep is too short.")
                return
            else:
                await self.sleep(sleep_time)
        self._base_time = current_time

    def _get_sleep_time(self):
        pass

    async def __call__(self, requested_sec: Union[int, float]) -> None:
        await self.wait(requested_sec)


def kwargs_parser(*args: str, kwargs: Optional[dict] = None):
    if kwargs is None:
        kwargs = inspect.currentframe().f_back.f_locals.get("kwargs")
        if not kwargs:
            return None
    keys = map(lambda key_: key_.lower(), kwargs.keys())
    args = map(lambda str_: str_.lower(), args)
    for arg in args:
        for key in keys:
            if arg in key:
                return kwargs[key]


class UIManager:
    pass


UIManagerTypes = Union[UIManager]  # , DiscordUIManager]
