from typing import Optional
import discord
from discord.ext.commands import command, Cog


class EmojiRegister(Cog):
    """Register attached image in message."""
    @command()
    async def register(self, ctx: discord.ext.commands.Context, name: Optional[str] = None) -> None:
        attachments = ctx.message.attachments
        if not attachments:
            return
        for attachment in attachments:
            if attachment.content_type.startswith("image"):
                byte_like = await attachment.read()
                name = name or attachment.filename.split(".")[0]
                if len(name) == 1:
                    name = f"{name}_"
                await ctx.guild.create_custom_emoji(name=name, image=byte_like)
                await ctx.send(f"Emoji is registered as {name}")
