from asyncio import sleep
from logging import getLogger, NullHandler
from textwrap import dedent
from typing import Optional

import discord.abc
from discord import HTTPException, Message

logger = getLogger(__name__)
logger.addHandler(NullHandler())


class SplitMessanger:
    """Split contents of message so that it's within limits, and
    send each message separately.

    Examples
    --------
    messanger = SplitMessanger(ctx, "first content")
    messanger += "second content"
    await messanger.send(delete_after=100)
    """
    LENGTH_LIMIT = 2000

    def __init__(self, messageable: discord.abc.Messageable,
                 content: str = "",
                 *,
                 splits_on_exactly_limit: bool = False,
                 joint="",
                 max_message_count: int = -1,
                 interval: int = 0):
        """
        Parameters
        ----------
        messageable : discord.abc.Messageable
            Destination of message. ex. TextChannel or Context
        content : str
            First contents of message. Assumes content will be added after construct.
        splits_on_exactly_limit : bool
            ex.
            1990 + 50
            If True,  => 2000, 40
            If False, => 1990, 50

            If True, each message should have exactly 2000 length except last message.
            If False, each added content doesn't get split in the middle of content.
            For example, if len 1990 already and you add 400 length contents,
            it is split as 1990 and 400. It should print emoji and mention well.
        joint : str
            String to joint each content in one message if content is within limit.
            "separator".join(each_contents)
        max_message_count : int
            Indicates the limit of number of message.
            -1 (default value) means no limit.

            If tries to send more amount of messages than this,
            logger.warnings is called and stopped to send messages.
        interval : int
            await asyncio.sleep(interval) between sending messages.
        """
        self.destination: discord.abc.Messageable = messageable
        self.contents: list[str] = [content] if content else []
        self.splits_on_limit: bool = splits_on_exactly_limit
        self.joint: str = joint
        self.max_message_count: int = max_message_count
        self.interval: int = interval

    def __add__(self, additional_content: str):
        if isinstance(additional_content, str):
            self.contents.append(additional_content)
            return self
        raise TypeError("Only str is accepted.")

    def __str__(self):
        return self.joint.join(self.contents)

    def __len__(self):
        return len(str(self))

    async def send(self, **kwargs) -> list[Optional[Message]]:
        """
        Send some messages with split contents.
        **kwargs are given for Messageable.send(**kwargs)
        """
        if len(self) == 0:
            return []
        elif len(self) <= self.LENGTH_LIMIT:
            return [await self.destination.send(str(self), **kwargs)]

        if self.splits_on_limit:
            split_list = self._split_by_length(str(self))
        else:
            split_list = self._split_on_addition()

        messages = []
        for i, content in enumerate(split_list, 1):
            if i > self.max_message_count > 0:
                log_message = dedent(f"""
                    Stopped to send some contents 
                    since it reaches the max count of sending message{self.max_message_count}.
                    Stopped contents are followings:\n""")
                for stopped_content in split_list[i:]:
                    log_message += f"{stopped_content[:15]}...{len(stopped_content)}\n"
                logger.info(log_message)
                break

            try:
                message = await self.destination.send(content, **kwargs)
            except Exception as e:
                already_sent_messages = messages
                await self.on_error(e, content, already_sent_messages)
            else:
                messages.append(message)
            finally:
                if i < self.max_message_count and i < len(split_list):
                    # if sends_next message
                    await sleep(self.interval)

        return messages

    def _split_on_addition(self):  # TODO var name
        split_content = ""
        split_list = []

        def add_current_content():
            nonlocal split_content
            if split_content:
                split_list.append(split_content)
                split_content = ""

        for content in self.contents:
            if len(content) > self.LENGTH_LIMIT:
                add_current_content()
                length_split_list = self._split_by_length(content)
                split_list += length_split_list[0:-1]
                split_content = length_split_list[-1]
                logger.info("Split a content by purely length since added single content is already over limit."
                            f"Content: {content[0:15]}...{len(content) - 15}chars")
            elif len(split_content) + len(content) + len(self.joint) > self.LENGTH_LIMIT:
                add_current_content()
                split_content = content
            else:
                split_content += self.joint + content
        add_current_content()
        return split_list

    @classmethod
    def _split_by_length(cls, content, length=LENGTH_LIMIT):
        split_list = []
        stop = length - 1
        for start in range(0, len(content), length):
            split_list.append(content[start:stop])
            stop = stop + length if stop + length < len(content) else len(content)
        return split_list

    async def on_error(self,
                       exception: Exception,
                       message_content: str,  # failed to send this
                       sent_messages  # messages sent already successfully
                       ):
        """Overwrite this if you want something on error while sending messages."""
        raise exception


async def delete(message: Message, **kwargs):
    try:
        await message.delete(**kwargs)
    except HTTPException:
        pass


async def update(message: Message, new_content: str, **kwargs):
    """Edit only if content is different from old one in order to avoid unnecessary API call."""
    if new_content != message.content:
        await message.edit(content=new_content, **kwargs)
    return message
