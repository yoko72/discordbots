from os import getcwd, environ
import logging
import argparse

import discord
from discord.ext.commands import Bot, Cog, command

from cogs import ChannelLinker
from cogs import EmojiTimer

logger = logging.getLogger(__name__)


def get_token(bot_name: str) -> str:
    """Get token from os.environ. If that var doesn't exist, then try to get from local file named config.py."""
    for var_name in [bot_name, bot_name + "_token", "token"]:
        token = environ.get(var_name, None)
        if token:
            return token
    try:
        from config import tokens
    except ImportError:
        try:
            from config import tokens
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


class HurryCog(ChannelLinker, EmojiTimer):
    LEFT_WORKING = "left_working"
    LEFT_SLEEPING = "left_sleeping"
    RIGHT = "right"
    WORK_MODE = "work"
    BREAK_MODE = "break"
    CHIME_PATH = getcwd() + "/sound/chime_with_fade_effects.wav"

    ids_dict = {  # voice_chat : text_chat
                863826970461995079:  # ぼちぼち(30分)
                863826907787034645,
                860542727003701289:  # メリハリ
                860561663597477889,
                862454402761621504:  # がっつり作業
                862454634488660008,
                864203551256870932:
                864203505983160340,
                853249947952087054:  # 実験鯖1
                853249961705734155,
                863043679450169354:  # 実験鯖2
                863043734080585750,
                578971953139023892:  # 倉庫
                564350361444286470
                }

    minutes_dict = {  # text_chat : minutes
        863826907787034645: 30,  # ぼちぼち
        860561663597477889: 60,  # メリハリ
        862454634488660008: 120,  # がっつり
        864203505983160340: 1,  # 実験
        564350361444286470: 1  # 倉庫
    }

    def __init__(self, bot_: Bot) -> None:
        ChannelLinker.__init__(self, bot_, self.ids_dict)
        EmojiTimer.__init__(self, bot_)

    @Cog.listener()
    async def on_ready(self) -> None:
        await EmojiTimer.on_ready(self)

    async def on_connect_to_targeted_vc(self, member: discord.Member, voice: discord.VoiceState) -> None:
        if member.bot:
            return
        text_channel_id = self.link_dict[voice.channel.id]
        channel = self.bot.get_channel(text_channel_id)
        logger.info(f"{member.name} joined {voice.channel.name}")
        await self.countdown(channel=channel)

    async def on_disconnect_from_targeted_vc(self, member: discord.Member, voice: discord.VoiceState) -> None:
        staying_members = voice.channel.members
        if staying_members:
            if any(map(lambda user: not user.bot, staying_members)):
                logger.debug(
                    f"{member.name} left from the voice channel, and it looks {staying_members} are still in the room.")
                return
        text_channel_id = self.link_dict[voice.channel.id]
        text_channel = bot.get_channel(text_channel_id)
        try:
            await self.stop(channel=text_channel)
        except KeyError:
            logger.warning(f"Failed to find timer although all members left from linked voice channel."
                           f"Maybe this member was in the voice channel before bot starts or something wrong happened.")
        voice_client = member.guild.voice_client
        if voice_client:
            await voice_client.disconnect(force=True)

    @command()
    async def countdown(self, ctx: discord.ext.commands.Context = None,
                        *, minutes: int = None, channel: discord.TextChannel = None, **kwargs) -> None:
        logger.debug("countdown started")
        channel = channel or ctx.channel
        if self._timer_dict.get(channel.id, None):
            return
        mode = kwargs.get("mode") or self.WORK_MODE
        minutes = minutes or self.get_minutes(channel, mode)
        await EmojiTimer.countdown(self, minutes=minutes, channel=channel, mode=mode)

    async def on_timer_finished(self, message: discord.Message, **kwargs) -> None:
        await self.play_chime(message.channel)
        await super().on_timer_finished(message)
        mode = kwargs.get("mode") or self.WORK_MODE
        if mode == self.BREAK_MODE:
            next_mode = self.WORK_MODE
        else:
            next_mode = self.BREAK_MODE
        next_minutes = self.get_minutes(message.channel, next_mode)
        await self.countdown(minutes=next_minutes, channel=message.channel, mode=next_mode)

    async def play_chime(self, channel: discord.TextChannel) -> None:
        for vc_id, tc_id in self.ids_dict.items():
            if channel.id == tc_id:
                voice_channel: discord.VoiceChannel = self.bot.get_channel(vc_id)
                break
        try:
            # noinspection PyUnboundLocalVariable
            voice_client: discord.VoiceClient = await voice_channel.connect()
        except discord.errors.ClientException as e:
            if e.args[0] == "Already connected to a voice channel.":
                # noinspection PyTypeChecker
                voice_client = channel.guild.voice_client
                if voice_client.channel != voice_channel:
                    await voice_client.disconnect()
                    try:
                        voice_client: discord.VoiceClient = await voice_channel.connect()
                    except discord.errors.ClientException:
                        raise

        # def my_after(error):
        #     if error:
        #         logger.warning(error)
        #     try:
        #         coro = voice_client.disconnect()
        #     except discord.errors.ClientException:
        #         pass
        #     # noinspection PyUnboundLocalVariable
        #     fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        #     # noinspection PyBroadException
        #     try:
        #         fut.result()
        #     except:
        #         pass

        try:
            # noinspection PyUnboundLocalVariable
            voice_client.play(self.get_music_source())  # after=my_after)
        except discord.errors.ClientException as e:
            if e.args[0] == 'Already playing audio.':
                pass
            else:
                raise

    @classmethod
    def get_music_source(cls) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(cls.CHIME_PATH)

    def get_minutes(self, channel: discord.TextChannel, mode: str = None) -> int:
        mode = mode or self.WORK_MODE
        if mode == self.BREAK_MODE:
            return 10
        elif self.minutes_dict.get(channel.id):
            return self.minutes_dict.get(channel.id)
        else:
            return 60

    @command()
    async def timer(self, ctx: discord.ext.commands.Context) -> None:
        """Alias of countdown"""
        await self.countdown(ctx)

    def convert_seconds_to_emojis(self, seconds: int, **kwargs) -> str:
        emojis_str_without_edges = EmojiTimer.convert_seconds_to_emojis(self, seconds)

        mode = kwargs.get("mode", None)
        if mode == self.WORK_MODE:
            left_edge = self._other_emojis[self.LEFT_WORKING]
        elif mode == self.BREAK_MODE:
            left_edge = self._other_emojis[self.LEFT_SLEEPING]
        else:
            raise Exception("No picture is specified.")
        right_edge = self._other_emojis[self.RIGHT]
        result_str = left_edge + emojis_str_without_edges + right_edge
        return result_str


if __name__ == "__main__":

    def main():
        # noinspection PyGlobalUndefined
        global bot
        parser = argparse.ArgumentParser()
        parser.add_argument("--log-level", default="WARNING", help="Log level for loggers")
        parser.add_argument("--bot-name", default="Hurry", help="Name of the bot to run")
        parser.add_argument("--bot-token", default=None, help="token of the bot")
        parser.add_argument("--prefix", default="!", help="Prefix of the bot command")
        args = parser.parse_args()
        log_level = getattr(logging, args.log_level)
        bot_name = args.bot_name
        token = args.bot_token
        prefix = args.prefix
        format_str = '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
        # noinspection PyArgumentList
        logging.basicConfig(encoding='utf-8', level=log_level, format=format_str)
        intents = discord.Intents.all()
        bot = Bot(prefix, intents=intents)
        cog = HurryCog(bot)
        bot.add_cog(cog)
        token = token or get_token(bot_name)

        async def load_emojis():
            await bot.wait_until_ready()
            cog = bot.get_cog("HurryCog")
            cog.build_emoji_dicts()

        bot.loop.create_task(load_emojis())
        bot.run(token)

    main()
