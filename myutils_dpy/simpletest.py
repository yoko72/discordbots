import unittest
from os import environ

from discord import Intents
from discord.ext.commands import Bot

bot = Bot("!", intents=Intents.all())


def test_global():
    print("global!")


class TestOne(unittest.TestCase):
    def test_case(self):
        print("case!")


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestOne("test_case"))
    testcase = unittest.FunctionTestCase(test_global)
    suite.addTest(testcase)
    return suite


@bot.event
async def on_ready():
    print("start")
    runner = unittest.TextTestRunner()
    runner.run(suite())
    print("false")
    # unittest.main()


token = environ["TEST_BOT_TOKEN"]
bot.run(token)
