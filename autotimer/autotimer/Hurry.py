import argparse
import logging
from pathlib import Path
from typing import Optional

import discord
import unicodedata
from discord.ext.commands import Bot, Cog, command, Context
from pandas import DataFrame
from utils.cogs.emoji_timer.emoji_timer import EmojiTimer
from utils.cogs.voice_text_linker import VoiceTextLinker
from utils.other import get_token

from .cogs.emoji_timer.countdown import CountDownTimer

logger = logging.getLogger(__name__)
from utils.cogs.emoji_register import EmojiRegister


# TODO 1. セーブできるようにする　２．時間を簡単かつ正確に　３．設定をプルダウンで

class HurryCog(VoiceTextLinker, EmojiTimer, EmojiRegister):
    LEFT_WORKING = "left_working"
    LEFT_SLEEPING = "left_sleeping"
    RIGHT = "right"
    WORK_MODE = "work"
    BREAK_MODE = "break"
    DYNAMIC = "dynamic"
    CHIME_PATH = Path() / "../sound/chime_5sec.wav"
    CHANNEL_SETTING_FILE = "../channels_settings.json"

    def __init__(self, bot_: Bot) -> None:
        VoiceTextLinker.__init__(self, bot_)
        EmojiTimer.__init__(self, bot_)

    def load_settings(self):
        VoiceTextLinker.load_settings(self)
        self.db = DataFrame(self.db)

    def get_tc(self, voicechat_id: int) -> Optional[discord.TextChannel]:
        tc_id = self._get_data("tc", vc=voicechat_id)
        return self.bot.get_channel(tc_id)

    def get_vc(self, textchat_id: int) -> discord.VoiceChannel:
        vc_id = self._get_data("vc", tc=textchat_id)
        return self.bot.get_channel(vc_id)

    def _get_work_minutes(self, voicechat_id: int) -> int:
        return self._get_data("work_minutes", vc=voicechat_id)

    def _get_break_minutes(self, voicechat_id: int) -> int:
        return self._get_data("break_minutes", vc=voicechat_id)

    def _get_data(self, target_data_name: str, **kwargs):
        key, val = kwargs.items().__iter__().__next__()
        filtered_df = self.db.query(f"{key} == {val}")
        return getattr(filtered_df, target_data_name)[0]

    @Cog.listener()
    async def on_ready(self) -> None:
        await EmojiTimer.on_ready(self)

    async def on_connect_to_targeted_vc(self,
                                        member: discord.Member,
                                        voice: discord.VoiceState,
                                        text_channel: discord.TextChannel) -> None:
        if member.bot:
            return
        logger.info(f"{member.name} joined {voice.channel.name}")
        await self.countdown(tc=text_channel)

    async def on_disconnect_from_targeted_vc(self,
                                             member: discord.Member,
                                             voice: discord.VoiceState,
                                             text_channel: discord.TextChannel) -> None:
        staying_members = voice.channel.members

        def user_remains():
            if staying_members:
                if any(map(lambda user: not user.bot, staying_members)):
                    return True
            return False

        if user_remains():
            logger.debug(f"{member.name} left from the voice channel, and {staying_members} are still in the room.")
            return
        try:
            timer: CountDownTimer = self._timer_dict[text_channel.id]
        except KeyError:
            logger.warning("A member left from linked voice channel, but task of countdown was not found. "
                           "The member might have been in the voice channel before bot starts maybe.")
        else:
            timer.stop()
            voice_client = member.guild.voice_client
            if voice_client:
                await voice_client.disconnect(force=True)

    @command()
    async def countdown(self, ctx: Context = None,
                        *, minutes: int = None, tc: discord.TextChannel = None, **kwargs) -> None:

        tc = tc or ctx.channel
        if self._timer_dict.get(tc.id, None):
            return
        logger.debug("countdown started")

        mode = kwargs.get("mode") or self.WORK_MODE
        if mode == self.WORK_MODE:
            self._set_timer_emoji(tc.id, self._other_emojis[self.LEFT_WORKING])
        elif mode == self.BREAK_MODE:
            self._set_timer_emoji(tc.id, self._other_emojis[self.LEFT_SLEEPING])
        minutes = minutes or self.get_minutes(tc, mode)
        if minutes:
            await EmojiTimer.countdown(self, minutes=minutes, channel=tc)

    async def on_timer_finished(self, message: discord.Message, **kwargs) -> None:
        voice_channel = self.get_vc(message.channel.id)
        await self.play_chime(voice_channel)
        await super().on_timer_finished(message)
        mode = kwargs.get("mode") or self.WORK_MODE
        if mode == self.BREAK_MODE:
            next_mode = self.WORK_MODE
        else:
            next_mode = self.BREAK_MODE
        next_minutes = self.get_minutes(message.channel, next_mode)
        if next_minutes:
            await self.countdown(minutes=next_minutes, tc=message.channel, mode=next_mode)

    async def play_chime(self, voice_channel: discord.VoiceChannel) -> None:
        try:
            voice_protocol: discord.VoiceProtocol = await voice_channel.connect()
        except discord.errors.ClientException as e:
            if e.args[0] == "Already connected to a voice channel.":
                # noinspection PyTypeChecker
                voice_protocol = channel.guild.voice_client
                if voice_protocol.channel != voice_channel:
                    await voice_protocol.disconnect(force=True)
                    try:
                        voice_protocol: discord.VoiceProtocol = await voice_channel.connect()
                    except discord.errors.ClientException:
                        raise

        # def my_after(error):
        #     if error:
        #         logger.warning(error)
        #     try:
        #         coro = voice_protocol.disconnect()
        #     except discord.errors.ClientException:
        #         pass
        #     # noinspection PyUnboundLocalVariable
        #     fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        #     # noinspection PyBroadException
        #     try:
        #         fut.result()
        #     except:
        #         pass

        # noinspection PyUnboundLocalVariable
        voice_protocol.play(self.get_music_source())  # after=my_after)

    @classmethod
    def get_music_source(cls) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(cls.CHIME_PATH)

    def get_minutes(self, tc: discord.TextChannel, mode: str = WORK_MODE) -> int:
        vc = self.get_vc(tc.id)
        if mode == self.WORK_MODE:
            return self._get_work_minutes(vc.id)
        elif mode == self.BREAK_MODE:
            return self._get_break_minutes(vc.id)

    def str_to_minutes(self,
                       string: str  # ex. "50", "50:15"
                       ) -> list:
        half_width_string = unicodedata.normalize('NFKC', string)
        if ":" in name:
            former, latter = name.split(":")
            if mode == self.WORK_MODE:
                return former
            elif mode == self.BREAK_MODE:
                return latter

    def get_minutes_from_name(self, channel: discord.TextChannel, mode):
        name = channel.name.replace("分", "")
        name = unicodedata.normalize('NFKC', name)
        if ":" in name:
            former, latter = name.split(":")
            if mode == self.WORK_MODE:
                return former
            elif mode == self.BREAK_MODE:
                return latter

    @command()
    async def timer(self, ctx: Context) -> None:
        """Alias of countdown"""
        await self.countdown(ctx)

    # def _convert_seconds_to_emojis(self, seconds: int, **kwargs) -> str:
    #     emojis_str_without_edges = EmojiTimer._convert_seconds_to_emojis(self, seconds)
    #
    #
    #     right_edge = self._other_emojis[self.RIGHT]
    #     result_str = left_edge + emojis_str_without_edges + right_edge
    #     return result_str

    @command()
    async def create(self, ctx: Context):
        await self.ask_minutes(ctx)

    async def ask_minutes(self, ctx):
        await ctx.send()


# class SelectMinutes(discord.ui)


if __name__ == "__main__":
    def main():
        # noinspection PyGlobalUndefined
        global bot
        parser = argparse.ArgumentParser()
        parser.add_argument("--log-level", default="WARNING", help="Log level for loggers")
        parser.add_argument("--name", default="Hurry", help="Name of the bot to run")
        parser.add_argument("--prefix", default="!", help="Prefix of the bot command")
        args = parser.parse_args()
        log_level = getattr(logging, args.log_level)
        bot_name = args.name
        prefix = args.prefix
        format_str = '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
        # noinspection PyArgumentList
        logging.basicConfig(encoding='utf-8', level=log_level, format=format_str)
        intents = discord.Intents.all()
        bot = Bot(prefix, intents=intents)
        cog = EmojiTimer(bot)
        bot.add_cog(cog)
        token = get_token(bot_name)
        print(bot_name, "started")
        bot.run(token)


    main()
