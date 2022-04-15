from os import environ

import discord
from discord.ext.commands import Bot, Cog


class TestCog(Cog):
    GUILD_ID_FOR_EMOJIS = "GUILD_ID_FOR_EMOJIS"
    GUILD_ID_TO_TEST = "GUILD_ID_TO_TEST"
    CHANNEL_ID_TO_TEST = "CHANNEL_ID_TO_TEST"

    def __init__(self, bot):
        self.bot: Bot = bot
        self.test_server: discord.Guild = None
        self.test_channel: discord.TextChannel = None

    @Cog.listener()
    async def on_ready(self):
        from test import test_content
        self.test_server = discord.utils.get(self.bot.guilds, id=int(environ[self.GUILD_ID_TO_TEST]))
        self.test_channel = discord.utils.get(self.test_server.channels, id=int(environ[self.CHANNEL_ID_TO_TEST]))
        print("on ready!")
        await test_content(self)

    async def _validate_author(self, ctx):
        return ctx.author.id in [381618666266951690, 747313058199896074]


def run_test():
    ENV_VAR_NAME_FOR_TOKEN = "TEST_BOT_TOKEN"
    PREFIX = "!"
    intents = discord.Intents.all()
    bot = discord.ext.commands.Bot(PREFIX, intents=intents)
    cog = TestCog(bot)
    bot.add_cog(cog)
    token = environ[ENV_VAR_NAME_FOR_TOKEN]
    bot.run(token)
