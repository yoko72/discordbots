import argparse
import inspect
import logging
import os
import sys
from typing import Callable

import discord

logger = logging.getLogger(__name__)


class CannotSpecifyMessage(Exception):
    pass


class NoMessagesStored(CannotSpecifyMessage):
    pass


class DefaultValueMaker(dict):
    """Represents similar class to defaultdict.
     This class can use key as arg of callable if key is not found."""

    def __init__(self, dict_: dict = None, key_not_found_handler: Callable = None):
        self.key_not_found_handler = key_not_found_handler
        if dict_ is None:
            dict_ = dict()
        super().__init__(self, **dict_)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            self[key] = self.on_key_not_found(key)
            return super().__getitem__(key)

    def on_key_not_found(self, key):
        """Require key_not_found_handler on __init__ or overridden on_key_not_found function."""
        if self.key_not_found_handler:
            return self.key_not_found_handler(key)
        else:
            raise Exception("Key was not found, and no handler was defined.")


class DiscordView:
    default_value_for_key = object()

    def __init__(self, channel, ForbiddenHandler: Callable = None, NotFoundHandler: Callable = None):
        self.channel = channel
        self.messages = {}

    async def send(self, content, key=None, **kwargs):
        key = key or self.default_value_for_key
        try:
            message = await self.channel.send(content, **kwargs)
        except discord.errors.Forbidden:
            logger.warning("Failed to send a message in a channel because of no permission."
                           f"{self._get_channel_info()}")
            return
        except discord.errors.NotFound:
            logger.warning("Failed to send a message in a channel since channel was not found."
                           f"{self._get_channel_info()}")
            return
        else:
            if key is not self.default_value_for_key:
                self.messages[key] = message
            return message

    def _get_channel_info(self):
        return f"channel_info {self.channel.id} {self.channel.name}"

    def _get_key(self, message):
        return [key for key, message_ in self.messages.items() if message == message_][0]

    async def update(self, content, message=None, key=None, **kwargs):
        """Message or key is required."""
        key = key or self.default_value_for_key
        try:
            message = message or self.messages[key]
        except KeyError:
            message = await self.send(content, **kwargs)
            if key is self.default_value_for_key:
                try:
                    key = self._get_key(message)  # message.content
                except KeyError:
                    return
            self.messages[key] = message
        else:
            await message.edit(content=content, **kwargs)

    async def put_reactions(self, emojis):
        pass

    async def clear_reactions(self, emojis):
        pass

    async def delete(self, message=None, key=None, **kwargs):
        """Require message or key."""
        key = key or self.default_value_for_key
        if key is not self.default_value_for_key:
            message = self.messages[key]
        try:
            await message.delete(**kwargs)
        except (discord.errors.NotFound, discord.errors.Forbidden):  # discord.HTTPException, AttributeErrorあたりも？
            pass
        if key is self.default_value_for_key:
            try:
                key = self._get_key(message)
            except KeyError:
                logger.warning(f"Key:{key} was not found in self.messages. Hence, ignored.")
        if key is not self.default_value_for_key:
            self._remove_from_stored(key)

    async def clear(self, **kwargs):
        for message in self.messages.values():
            await self.delete(message, **kwargs)

    def _remove_from_stored(self, key):
        try:
            del self.messages[key]
        except KeyError:
            logger.warning(f"Failed to find message in self.messages by specified key."
                           f"specified key: {key}."
                           "Hence, self.messages didn't change at all.")


parser = argparse.ArgumentParser()


def set_commandline_args(*args, **kwargs):
    if args or kwargs:
        parser.add_argument(*args, **kwargs)
    else:
        parser.add_argument("--log-level", default="warning", help="Log level for logger")


def get_commandline_args(*names):
    args = parser.parse_args()
    arg_list = []
    for name in names:
        arg = getattr(args, name)
        arg_list.append(arg)
    return arg_list


ON_PAAS = "on_PaaS"


def set_logger(*loggers, log_level, dir_name=None):
    if not dir_name:
        frame = inspect.currentframe().f_back
        filename = frame.f_globals["__file__"]
        filename = filename.split("/")[-1].split(".")[0]  # /path/to/file_name.py -> file_name
        dir_name = filename
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    ch.setFormatter(formatter)
    for logger in loggers:
        logger.setLevel(log_level)
        logger.addHandler(ch)
        if not os.environ.get(ON_PAAS, None):
            fh = logging.FileHandler(f'{dir_name}_logs/{logger.name}.log', encoding="utf-8", mode="w")
            fh.setLevel(log_level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)


def get_log_level(string: str):
    if string:
        return getattr(logging, string.upper())
    else:
        if sys.gettrace() is None:
            return logging.DEBUG
        else:
            return logging.WARNING


def get_token(bot_name):
    try:
        from . import myinfo
    except ModuleNotFoundError:
        from os import environ
        token = environ[f"{bot_name}"]
    else:
        token = getattr(myinfo.tokens, bot_name)
    return token
