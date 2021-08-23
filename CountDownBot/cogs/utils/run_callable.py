from typing import Optional, Callable
from inspect import iscoroutinefunction


async def run_callable(callable_: Optional[Callable], *args, **kwargs):
    if callable_ is None:
        return
    elif iscoroutinefunction(callable_):
        return await callable_(*args, **kwargs)
    else:
        return callable_(*args, **kwargs)