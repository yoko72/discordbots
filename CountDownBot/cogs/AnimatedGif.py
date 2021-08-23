#
# class AnimatedGif(Cog):  # not working yet
#     def __init__(self, bot):
#         super().__init__(bot)
#         self.bot = bot
#         self.gif_emojis = {}
#
#     @Cog.listener()
#     async def on_ready(self):
#         for emoji in self.bot.emojis:
#             if emoji.animated:
#                 self.gif_emojis[emoji.name] = emoji
#
#
# class AnimatedGifTimer(EmojiTimer):
#     PREFIX_OF_GIF = "count"
#     DEFAULT_TIMING_OF_EDITING_GIF = (9, 5, 2)
#
#     def store_emoji(self, emoji):
#         if emoji.animated and emoji.name.startswith(self.PREFIX_OF_GIF):
#             self.gif_emojis[emoji.name] = str(emoji)
#         else:
#             super().store_emoji(emoji)
#
#     def convert_seconds_to_emojis(self, seconds):
#         super_result = super().convert_seconds_to_emojis(seconds)
#         splited = super_result.split(">")
#         restored = map(lambda x: x+">", splited)