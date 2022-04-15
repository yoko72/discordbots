from datetime import datetime, timedelta


class CountDownTimer:
    """Pseudo timer as if it countdowns.
    It just calculates time gap between requested time and actually spent time.
    """
    now = datetime.now

    def __init__(self, seconds: int):
        self.__requested_seconds = seconds
        self.__remaining_seconds = seconds
        self.__is_stopped = False
        self.started_time = self.last_time = self.now()

    @property
    def remaining_seconds(self):
        if self.is_stopped:
            return self.__remaining_seconds
        spent_time: timedelta = self.now() - self.started_time
        self.__remaining_seconds = self.__requested_seconds - spent_time.total_seconds()
        return self.__remaining_seconds

    @remaining_seconds.setter
    def remaining_seconds(self, val):
        if val < 0:
            raise ValueError(f"The amount of seconds must be bigger than 0, but {val} was given.")
        self.__requested_seconds = val

    @property
    def delta_seconds(self) -> float:
        now = self.now()
        delta: timedelta = now - self.last_time
        self.last_time = now
        return delta.total_seconds()

    def set_base_time(self, time: datetime = None):
        if time is None:
            time = self.now()
        self.last_time = time

    @property
    def is_stopped(self):
        return self.__is_stopped

    def stop(self):
        self.__is_stopped = True

    class NotStopped(Exception):
        pass

    class Stopped(Exception):
        pass

    def resume(self):
        if not self.is_stopped:
            raise self.NotStopped
        self.__requested_seconds = self.__remaining_seconds
        self.__is_stopped = False
        self.started_time = self.now()
