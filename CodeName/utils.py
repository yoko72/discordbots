import threading
import asyncio
import inspect
from collections.abc import Callable
from typing import Optional, Union
import logging

import discord

num_emojis = ['0⃣', '1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣', '9⃣']
num_zenkakus = ['０', '１', '２', '３', '４', '５', '６', '７', '８', '９']
num_kanjis = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']

for_std_num_trans = str.maketrans("".join([char1+char2 for char1, char2 in zip(num_zenkakus, num_kanjis)]),
                                  "".join([str(i)+str(i) for i in range(10)]))

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
    _counting_task: Optional[asyncio.Task] = None
    _counted_sec = 0
    _active_instances = list()

    def __init__(self, loop_sleep_sec: float = 0.1):
        cls = AioDeltaSleeper
        self._last_sec: int = cls._counted_sec
        self._wait_task: Optional[asyncio.Task] = None
        self._loop_sleep_sec = loop_sleep_sec
        cls._active_instances.append(self)

        if cls._counting_task is None:
            cls._counting_task = asyncio.create_task(cls.count())

    async def wait(self, requested_sec) -> None:

        async def wait_task():
            delta = self._get_delta()
            remaining_sleep_sec = requested_sec - delta
            if remaining_sleep_sec <= 0:
                return
            elif int(remaining_sleep_sec) > 1:
                # ex.  wait for 3 seconds if this should sleep for approximately 3.5 secs
                await asyncio.sleep(int(remaining_sleep_sec) - 1)
            while self._get_delta() < requested_sec:
                await asyncio.sleep(self._loop_sleep_sec)
            self._last_sec = self._counted_sec

        self._wait_task = asyncio.create_task(wait_task())
        await self._wait_task

    def _get_delta(self):
        return AioDeltaSleeper._counted_sec - self._last_sec

    def cancel_wait(self):
        self._wait_task.cancel()

    @classmethod
    def cancel_count(cls):
        logger.debug(f"Counting of {cls.__name__} is cancelled.")
        cls._counting_task.cancel()
        cls._counting_task = None

    @classmethod
    async def count(cls):
        logger.debug(f"Counting of {cls.__name__} has started.")
        while True:
            await asyncio.sleep(1)
            cls._counted_sec += 1

    def __enter__(self) -> "AioDeltaSleeper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel_wait()
        try:
            AioDeltaSleeper._active_instances.remove(self)
        except ValueError:
            pass
        if not AioDeltaSleeper._active_instances:
            self.cancel_count()


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
