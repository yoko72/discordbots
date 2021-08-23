import logging
from typing import Optional

import discord
from discord.ext.commands import Cog, command
import pykakasi

logger = logging.getLogger(__name__)
kks = pykakasi.kakasi()


class AvatarEmojiRegister(Cog):
    DEFAULT_GUILD_ID = 853249947952087050  # 実験鯖
    kks_converter = kks

    def __init__(self, bot: discord.ext.commands.Bot) -> None:
        self.bot: discord.ext.commands.Bot = bot
        self._guild: discord.Guild = bot.get_guild(self.DEFAULT_GUILD_ID)

    @command()
    async def register(self, ctx: discord.ext.commands.Context = None,
                       member: discord.Member = None, guild: discord.Guild = None, **kwargs) -> Optional[discord.Emoji]:
        if ctx and isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("You cannot ask me to register your avatar image as emoji, "
                           "since I don't know which guild you want to register.")
            return None
        member: discord.Member = member or ctx.author
        obj_for_guild = ctx or member or self
        guild = guild or obj_for_guild.guild
        avatar = member.avatar
        bytes_ = await avatar.read()
        name_for_emoji: str = self.get_ascii_name(member)
        try:
            return await guild.create_custom_emoji(name=name_for_emoji, image=bytes_, **kwargs)
        except discord.errors.HTTPException as e:
            if e.code == 30008:  # Reaches the limit count of emoji.
                logger.info(e.text)
            elif e.code == 50035:  # 'Invalid Form Body In name: String value did not match validation regex.'
                logger.info(f"{name_for_emoji} was not valid name to register as emoji.")
                emoji_name = str(member.id)
                return await guild.create_custom_emoji(name=emoji_name, image=bytes_, **kwargs)

    def get_ascii_name(self, member: discord.Member) -> str:
        for name in [member.nick, member.name]:
            if not name:
                continue

            if name.encode("utf-8").isalnum():
                return name
            else:
                name = "".join([item["hepburn"] or item["orig"] for item in self.kks_converter.convert(name)])
                if name.encode("utf-8").isalnum():
                    return name
                else:
                    continue
        # if both of nickname and name include characters which is not non-ASCII, Japanese
        return str(member.id)

    def load_emoji(self):
        pass

    async def get_avatar_emoji(self, member: discord.Member, **kwargs) -> Optional[discord.Emoji]:
        name = self.get_ascii_name(member)
        for emoji in member.guild.emojis:
            if emoji.name == name:
                return emoji

        try:
            emoji = await self.register(member=member, **kwargs)
        except (discord.errors.Forbidden, discord.errors.HTTPException) as e:
            logger.warning(e)
            return None
        else:
            return emoji

    @property
    def guild(self) -> discord.Guild:
        limits = self._guild.emoji_limit
        emoji_count = len(self._guild.emojis)
        if limits <= emoji_count:
            self.guild = self.get_another_guild()
        return self._guild

    @guild.setter
    def guild(self, value: discord.Guild) -> None:
        self._guild = value

    def get_another_guild(self) -> discord.Guild:
        return self.bot.get_guild(564350361444286464)
