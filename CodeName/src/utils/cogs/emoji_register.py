from functools import lru_cache
from typing import Optional

import discord
from discord.ext.commands import command, Cog


class EmojiLoader(Cog):
    def __init__(self, bot, id_of_guild: int):
        super().__init__()
        self.bot = bot
        self.__id_of_emoji_storage_guild = id_of_guild

    @property
    @lru_cache()
    def guild_storing_emoji(self):
        return self.bot.get_guild(self.__id_of_emoji_storage_guild)

    def get_emoji(self, emoji_name):
        return discord.utils.get(self.bot.emojis, name=emoji_name, guild=self.guild_storing_emoji)


class EmojiRegister(Cog):
    """Register all images attached in message."""

    @command()
    async def register(self, ctx: discord.ext.commands.Context, name: Optional[str] = None) -> None:
        attachments = ctx.message.attachments
        if not attachments:
            await ctx.send(f"Noe emoji was found.")
        for attachment in attachments:
            if attachment.content_type.startswith("image"):
                byte_like = await attachment.read()
                name = name or attachment.filename.split(".")[0]
                if len(name) == 1:
                    name = f"{name}_"
                await ctx.guild.create_custom_emoji(name=name, image=byte_like)
                await ctx.send(f"Emoji is registered as {name}")
