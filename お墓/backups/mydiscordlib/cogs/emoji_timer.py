import asyncio
import logging
from typing import Optional, Dict

import discord
from discord.ext.commands import Cog, command

from ..utils.countdown import AioDeltaCountdown

logger = logging.getLogger(__name__)


class EmojiTimer(Cog):
    SUFFIX_OF_PIC_FOR_2ND_LEFT = "colon"
    SUFFIX_OF_PIC_FOR_2ND_RIGHT = "right"
    SUFFIX_OF_NORMAL_PIC = "_"
    DEFAULT_MINUTES = 60
    MESSAGE_KEY = "timer"

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self._timer_dict: Dict[int: AioDeltaCountdown] = {}
        self._message_dict: Dict[int: discord.Message] = {}
        self._center_aligned_num_emojis = {}
        self._num_with_colon_emojis = {}
        self._right_aligned_num_emojis = {}
        self._other_emojis = {}

    @Cog.listener()
    async def on_ready(self) -> None:
        self._build_emoji_dicts()

    def _build_emoji_dicts(self) -> None:
        for emoji in self.bot.emojis:
            self._store_emoji(emoji)

    def _store_emoji(self, emoji: discord.Emoji) -> None:
        emoji_str = str(emoji)
        try:
            integer = int(emoji.name[0])
        except ValueError:
            self._other_emojis[emoji.name] = emoji_str
        else:
            if self.SUFFIX_OF_PIC_FOR_2ND_LEFT in emoji.name:
                self._num_with_colon_emojis[integer] = emoji_str
            elif self.SUFFIX_OF_PIC_FOR_2ND_RIGHT in emoji.name:
                self._right_aligned_num_emojis[integer] = emoji_str
            elif emoji.name.endswith(self.SUFFIX_OF_NORMAL_PIC):
                self._center_aligned_num_emojis[integer] = emoji_str

    # @discord.ext.commands.max_concurrency is not enough
    # since following func can run from non-command actions in derived class.
    @command()
    async def countdown(self, ctx: discord.ext.commands.Context = None,
                        *, minutes: Optional[int] = None, channel: Optional[discord.TextChannel] = None, **kwargs):
        logger.info("Countdown started")
        channel = channel or ctx.channel
        minutes = int(minutes) or self.DEFAULT_MINUTES
        seconds = minutes * 60
        sentence = self._convert_seconds_to_emojis(seconds, **kwargs)
        message = kwargs.get("message", None) \
                  or self._message_dict.get(channel.id, None) \
                  or await channel.send(sentence)
        async with AioDeltaCountdown(seconds=seconds) as timer:
            self._timer_dict[channel.id] = timer
            while timer.seconds > 0:
                try:
                    await timer.wait_count(1)
                except timer.SpecifiedTimeAlreadyPassed:
                    pass
                except timer.Cancelled:
                    self._delete_from_dicts(channel)
                    await message.delete(delay=0)
                    return
                except timer.Paused:
                    return
                else:
                    try:
                        await self.on_every_second(timer.seconds, message, **kwargs)
                    except Exception as e:
                        logger.warning(str(e))
                        continue
            self._delete_from_dicts(channel)
            logger.info("Countdown started")
            await self.on_timer_finished(message, **kwargs)

    async def on_every_second(self, remaining_seconds: int, message: discord.Message, **kwargs) -> None:
        try:
            await message.edit(content=self._convert_seconds_to_emojis(remaining_seconds, **kwargs))
        except discord.errors.NotFound:
            await message.channel.send(self._convert_seconds_to_emojis(remaining_seconds, **kwargs))

    def _convert_seconds_to_emojis(self, seconds: int, **kwargs) -> str:
        # Accept kwargs so that child class can utilize other args
        minutes, seconds = divmod(seconds, 60)
        time_str = "{:0>2}{:0>2}".format(minutes, seconds)
        str_length = len(time_str)
        emojis_str = ""
        for i, num_str in enumerate(time_str):
            digit_place = str_length - i
            num = int(num_str)
            if digit_place == 3:
                emojis_str += self._num_with_colon_emojis[num]
            elif digit_place == 2 or digit_place > 4:
                emojis_str += self._right_aligned_num_emojis[num]
            else:
                emojis_str += self._center_aligned_num_emojis[num]
        return emojis_str

    async def on_timer_finished(self, message: discord.Message, **kwargs) -> None:
        await asyncio.sleep(3)
        await message.delete(delay=0)

    @command()
    async def stop(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer: AioDeltaCountdown = self._timer_dict[channel.id]
        timer.cancel()
        self._delete_from_dicts(channel)

    @command()
    async def pause(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer: AioDeltaCountdown = self._timer_dict[channel.id]
        timer.pause()

    @command()
    async def resume(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer: AioDeltaCountdown = self._timer_dict[channel.id]
        if timer.is_paused:
            timer.resume()
        else:
            await channel.send("pauseされてないよ！", delete_after=10)

    def _delete_from_dicts(self, channel: discord.TextChannel) -> None:
        try:
            del self._timer_dict[channel.id]
        except KeyError:
            pass
        try:
            del self._message_dict[channel.id]
        except KeyError:
            pass
