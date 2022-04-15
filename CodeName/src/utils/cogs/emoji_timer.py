import asyncio
import logging
from math import modf
from typing import Optional, Dict

import discord
from discord.ext.commands import command
from utils import messaging
from utils.emoji_loader import EmojiLoaderCog
from utils.inner_timer import CountDownTimer

logger = logging.getLogger(__name__)


class CustomEmojiTimerCog(EmojiLoaderCog):
    SUFFIX_OF_LEFT_ALIGN = "_with_colon"
    SUFFIX_OF_RIGHT_ALIGN = "_right_align"
    SUFFIX_OF_RIGHTMOST = "_rightmost"
    SUFFIX_OF_CENTER_ALIGN = "_"  # Discord adds "_" to the name of emoji if it is only 1 digit num.

    suffixes_of_images: dict[int:str] = {
        1: SUFFIX_OF_RIGHTMOST, 2: SUFFIX_OF_RIGHT_ALIGN,
        3: SUFFIX_OF_LEFT_ALIGN, 4: SUFFIX_OF_CENTER_ALIGN
    }
    # Key int indicates digit place(桁数) for num emoji.
    DEFAULT_MINUTES = 60
    DEFAULT_TIMER_ICON_NAME = "hourglass"

    def __init__(self, bot,
                 id_of_emoji_storage_guild: int,
                 minimum_interval_to_edit: float = 0.3) -> None:
        EmojiLoaderCog.__init__(self, bot, id_of_emoji_storage_guild)

        self._timer_dict: Dict[int: CountDownTimer] = {}
        self._message_dict: Dict[int: discord.Message] = {}
        self.min_interval = minimum_interval_to_edit

    def get_timer(self, textchannel_id: int) -> CountDownTimer:
        return self._timer_dict.get(textchannel_id)

    def set_timer(self, textchannel_id: int, task: CountDownTimer):
        self._timer_dict[textchannel_id] = task

    # @discord.ext.commands.max_concurrency is not enough
    # since following func can run from non-command actions in derived class.
    @command()
    async def countdown(self, ctx: discord.ext.commands.Context = None,
                        *, minutes: Optional[int] = None, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        logger.info(f"Countdown started in channel: {channel.name}")
        minutes = int(minutes) or self.DEFAULT_MINUTES
        seconds = minutes * 60
        sentence = self._build_timer_strings(seconds)
        timer = CountDownTimer(seconds=seconds)
        self.set_timer(channel.id, timer)
        message = self._message_dict[channel.id] = await channel.send(sentence)
        try:
            await self.loop_count(message, timer)
        except timer.NotStopped:
            pass
        else:
            await self.on_timer_finished(self._message_dict[channel.id])

    async def loop_count(self, message, timer):
        """
        Edit message to current remaining seconds continuously.

        Raises
        ------
        CountDownTimer.Stopped
        """
        while timer.remaining_seconds > 0:
            timer.set_base_time()
            seconds = int(timer.remaining_seconds)
            message = await self.update_timer_message(seconds, message)
            delta = round(timer.delta_seconds, ndigits=2)
            # Sleep till next edit in order to avoid rate limit.
            fractional, _ = modf(delta)
            wait_time = 1 - fractional
            if wait_time < self.min_interval:
                wait_time = self.min_interval
            await asyncio.sleep(wait_time)
            if delta > 2:
                channel = message.channel
                logger.warning(f"So laggy. Editing message took {delta} seconds "
                               f"in channel: {channel.name} guild: {channel.guild.name} {channel.id}.")
            if timer.is_stopped:
                raise timer.Stopped()
        else:
            await self.update_timer_message(0, message)

    async def update_timer_message(self, remaining_seconds: int, message: discord.Message) -> discord.Message:
        new_content = self._build_timer_strings(remaining_seconds)
        try:
            await messaging.update(message, new_content)
        except discord.errors.NotFound:
            if self._timer_dict.get(message.channel.id, None) is not None:
                # if somebody deleted the timer message without stop command
                message = await message.channel.send(new_content)
        finally:
            return message

    def _build_timer_strings(self, seconds: int, **kwargs) -> str:
        timer_icon = self.get_timer_icon(**kwargs)
        sentence = "".join([str(timer_icon)] + self._seconds_to_emojis(seconds))
        return sentence

    def get_timer_icon(self, **kwargs):
        return self.get_emoji(emoji_name=self.DEFAULT_TIMER_ICON_NAME)

    def _seconds_to_emojis(self, seconds) -> list[str]:
        minutes, seconds = divmod(seconds, 60)
        time_str = "{:0>2}{:0>2}".format(minutes, seconds)
        emojis = []
        for i, num_str in enumerate(time_str[-1::-1], start=1):
            emojis.append(str(self._get_num_emoji(num_str, digit_place=i)))
        return emojis[-1::-1]

    def _get_num_emoji(self, num_str: str, digit_place: int):
        """
        Parameters
        ----------
        digit_place: int
            ex. Digit_place of "7" in "3759" is 3. 桁。十の位なら2。
        """
        if digit_place > 4:  # if given time is enormous like 32:45:60
            digit_place = digit_place % 4  # slide digit
            if digit_place == 1:
                digit_place = 4
        emoji_name = num_str + self.suffixes_of_images[digit_place]
        return self.get_emoji(emoji_name=emoji_name)

    async def on_timer_finished(self, message: discord.Message, delay=3, **kwargs) -> None:
        await messaging.delete(message, delay=delay)
        self._clear_dicts(message.channel)
        logger.info(f"Countdown successfully finished in channel: {channel.name}")

    @command()
    async def stop(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer = self.get_timer(channel.id)
        timer.stop()
        message = self._message_dict[channel.id]
        self._clear_dicts(channel)
        try:
            await message.delete()
        except discord.NotFound:
            pass

    @command()
    async def pause(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer: CountDownTimer = self.get_timer(channel.id)
        timer.stop()

    @command()
    async def resume(self, ctx: discord.ext.commands.Context, *, channel: discord.TextChannel = None) -> None:
        channel = channel or ctx.channel
        timer: CountDownTimer = self.get_timer(channel.id)
        if timer and timer.is_stopped:
            timer.resume()
            message = self._message_dict.get(channel.id)
            await self.loop_count(message, timer)
            await self.on_timer_finished(message)
        elif not timer:
            await channel.send("TimerTaskNotFound!", delete_after=10)
        elif not timer.is_stopped:
            await channel.send("No timer is paused!", delete_after=10)

    def _clear_dicts(self, channel: discord.TextChannel) -> None:
        for _dict in [self._timer_dict, self._message_dict]:
            try:
                del _dict[channel.id]
            except KeyError:
                pass
