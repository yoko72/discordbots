import json
from pathlib import Path
from typing import Dict, Optional

import discord
from discord.ext.commands import Cog, command


# noinspection SpellCheckingInspection
class VoiceTextLinker(Cog):
    """Associate voice channel and text channel.
    When a member connects to specified channels, events happen with associated text chat.
    """
    CHANNEL_SETTING_FILE = "channels_settings.json"
    VOICECHANNEL_NOTFOUND = "Make sure you are in a voice channel before the command!" \
                            "If you surely are in a voice channel, I cannot see it."
    SUCCESSFULLY_LINKED = "🔊{voice_channel_name} is linked with ✏{text_channel_name} now!"
    LINK_SAME = "This text chat is already linked with your current voice chat."
    LINK_OTHER = "Your current voice channel was already linked with ✏{text_channel_name}." \
                 "To link with this text channel, past one is removed."

    def __init__(self, bot: discord.ext.commands.Bot,
                 db: Dict = None, setting_json_path: str = None, saves_settings=True) -> None:
        """
        Parameters
        ----------
        db : Dict[int:int]
            Key int should be id of voicechannel, value should be id of textchannel.
        setting_json_path : str
            Path of json file about setting. e.g. "/currentpath/settings/file.json", "file.json".
            The json file should only have 1 associative array. Key is id of voicechannel, value is id of textchannel.
        saves_settings : boolean
            If True, the bot saves settings as json and can load it even after reboot.
        """
        self.bot = bot
        if db:
            self.db = db
        else:
            self.db = {}

        self.does_save = True
        if setting_json_path:
            self.setting_json_path = Path(setting_json_path)
        else:
            self.setting_json_path = Path(self.CHANNEL_SETTING_FILE)
        self.make_sure_file_exists()
        self.load_settings()

        super().__init__(bot)

    def make_sure_file_exists(self):
        if not self.does_save:
            return
        if not self.setting_json_path.exists():
            self.save_settings()

    def load_settings(self):
        with self.setting_json_path.open(mode="r") as f:
            self.db.update(json.load(f))

    def save_settings(self, content: Optional[Dict] = None):
        if content:
            self.db.update[content]
        with self.setting_json_path.open(mode="w") as f:
            json.dump(self.db, f)

    @command()
    async def link(self, ctx: discord.ext.commands.Context, **kwargs) -> None:
        if not ctx.author.voice:
            await self.on_voicechannel_not_found(ctx)
        voice_channel = ctx.author.voice.channel

        linked_textchat = self.get_tc(voice_channel.id)
        if linked_textchat:
            if linked_textchat.id == ctx.channel.id:
                await self.on_link_same(ctx, voice_channel)
            elif is_linked_already():
                await self.on_link_other(ctx, voice_channel)
        else:
            await self.on_link_successfully(ctx, voice_channel)

    async def on_voicechannel_not_found(self):
        await ctx.send(self.VOICECHANNEL_NOTFOUND)

    async def on_link_successfully(self, ctx, vc):
        self.db[voice_channel.id] = ctx.channel.id
        await ctx.send(self.SUCCESSFULLY_LINKED.format(voice_channel_name=vc.name, text_channel_name=ctx.channel.name))

    async def on_link_same(self, ctx, vc):
        await ctx.send(self.LINK_SAME)

    async def on_link_other(self, ctx, vc):
        await ctx.send(self.LINK_OTHER)
        await self.on_link_successfully(ctx, vc)

    def get_vc(self, textchat_id: int) -> discord.VoiceChannel:
        vc_id = [vc_id for vc_id, tc_id in self.db.items() if textchat_id == tc_id][0]
        vc = self.bot.get_channel(vc_id)
        return vc

    def get_tc(self, voicechat_id: int) -> Optional[discord.TextChannel]:
        text_id = self.db.get(voicechat_id, None)
        if text_id is not None:
            return self.bot.get_channel(text_id)

    @Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        if before.channel == after.channel:
            return
        if before.channel:
            textchannel = self.get_tc(before.channel.id)
            if textchannel:
                await self.on_disconnect_from_targeted_vc(member, before, textchannel)
        if after.channel:
            textchannel = self.get_tc(after.channel.id)
            if textchannel:
                await self.on_connect_to_targeted_vc(member, after, textchannel)

    async def on_connect_to_targeted_vc(self,
                                        member: discord.Member,
                                        connected_voice: discord.VoiceState,
                                        textchannel: discord.TextChannel) -> None:
        pass

    async def on_disconnect_from_targeted_vc(self,
                                             member: discord.Member,
                                             disconnected_voice: discord.VoiceState,
                                             textchannel: discord.TextChannel) -> None:
        pass
