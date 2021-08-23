from typing import Dict

from discord.ext.commands import Cog, command
import discord


# noinspection SpellCheckingInspection
class ChannelLinker(Cog):
    """Associate voice chat and text chat.
    When a member connects to specified channels, events happen with associated text chat."""
    def __init__(self, bot: discord.ext.commands.Bot, dict_of_ids: Dict[int, int]) -> None:
        """Key should be id of VC, value should be id of TC."""
        self.bot = bot
        self.link_dict: Dict[int, int] = dict_of_ids
        super().__init__(bot)

    @command()
    async def link(self, ctx: discord.ext.commands.Context) -> None:
        if not ctx.author.voice:
            return
        tc_id = self.link_dict.get(ctx.author.voice.channel.id, None)
        if tc_id:
            await ctx.send("This text chat is already linked with your current voice chat.")
        else:
            self.link_dict[ctx.author.voice.channel.id] = ctx.channel.id

    @Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        if before.channel == after.channel:
            return
        if after.channel:
            if after.channel.id in self.link_dict.keys():
                await self.on_connect_to_targeted_vc(member, after)
        if before.channel:
            if before.channel.id in self.link_dict.keys():
                await self.on_disconnect_from_targeted_vc(member, before)

    async def on_connect_to_targeted_vc(self, member: discord.Member, voice: discord.VoiceState) -> None:
        pass

    async def on_disconnect_from_targeted_vc(self, member: discord.Member, voice: discord.VoiceState) -> None:
        pass
