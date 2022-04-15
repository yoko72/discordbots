import pickle

from discordbots.tests.test_base import run_test, TestCog


async def test_content(self: TestCog):
    guild = self.bot.guilds[0]
    emojis = guild.emojis
    sample_emoji = emojis[0]
    with open("here", mode="w") as f:
        pickle.dump(sample_emoji, f)


if __name__ == "__main__":
    run_test()
