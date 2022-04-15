import inspect
import logging
from os import environ
from typing import Optional, Callable

logger = logging.getLogger(__name__)


def get_token(bot_name: str) -> str:
    """Get token from os.environ. If it is specified, then try to get from local file named myinfo."""
    token = environ.get(bot_name, None)
    if token:
        return token
    try:
        from myinfo import tokens
    except ImportError:
        try:
            from .myinfo import tokens
        except ImportError:
            logger.error("Failed to find tokens from neither os.environ or local file."
                         "Local file should be named as myinfo.")
            raise
    token = tokens.get(bot_name, None)
    if not token:
        logger.error("Failed to find tokens from neither os.environ or local file."
                     "Local file should be named as myinfo.")
        raise Exception
    return token


async def run_callable(callable_: Optional[Callable], *args, **kwargs):
    if callable_ is None:
        return
    elif inspect.iscoroutinefunction(callable_):
        return await callable_(*args, **kwargs)
    else:
        return callable_(*args, **kwargs)
