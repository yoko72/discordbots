import discord
from autotimer.utils.cogs import emoji_timer, emoji_register
from autotimer.utils.other import get_token

register = emoji_register.EmojiRegister
timer = emoji_timer.EmojiTimer

intents = discord.Intents.all()
bot = discord.ext.commands.Bot("!", intents=intents)
# cog_name = clappy.parse("--cog", choices=["register", "timer"])
# cog_class = globals[cog_name]
bot.add_cog(timer(bot, 853249947952087050))
token = get_token("Mary")
bot.run(token)
