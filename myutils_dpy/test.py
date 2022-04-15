import functools
import pickle
from os import environ

from discord import Intents
from discord.ext.commands import Bot, Cog, command, Command

bot = None
suites = []
DEFAULT_PREFIX = "!"


def set_bot(*args, **kwargs):
    global bot
    bot = Bot(*args, **kwargs)


def _ensure_bot_instance_exists(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        global bot
        if bot is None:
            bot = Bot(DEFAULT_PREFIX, intents=Intents.all())
        return f(*args, **kwargs)

    return inner


def add_suites(*callables):
    global suites
    for callable in callables:
        suites.append(callable)


@_ensure_bot_instance_exists
def add_cogs(*cogs):
    global bot
    for cog in cogs:
        bot.add_cog(cog)


@_ensure_bot_instance_exists
def auto_run():
    global bot, suites
    if bot is None:
        bot = Bot(DEFAULT_PREFIX, intents=Intents.all())

    @bot.event
    async def on_ready():
        for suite in suites:
            if isinstance(suite, Command):
                cog_cls = AutoCommandCog
            elif isinstance(suite, discord.event):
                pass
        cog_cls = AutoTestCog

    bot.add_cog(cog_cls(bot, test_func, **kwargs))
    token = environ["TEST_BOT_TOKEN"]
    bot.run(token)


class AutoTestCog(Cog):
    def __init__(self, bot, test_func, **kwargs):
        self.bot: Bot = bot
        self.test_func = test_func
        self.kwargs_for_test_func = kwargs

    async def run(self):
        if self.kwargs_for_test_func:
            result = await self.test_func(**self.kwargs_for_test_func)
        else:
            result = await self.test_func()
        return result

    @Cog.listener()
    async def on_ready(self):
        print("on_ready! Starting test...")
        await self.run()
        print("Finished test!")

    async def find_test_env(self):
        required_args = self.test_func


class AutoCommandCog(AutoTestCog):
    SAVED_CONTEXT_FILENAME = "test_ctx"

    async def run(self):
        ctx = self.load_context()
        if ctx:
            result = await self.test_func(ctx)
        else:
            result = None
            print(f"No context is saved. Invoke {self.bot.command_prefix}{self.save_context.name} first.")
        return result

    @command()
    async def save_context(self, context):
        with open(self.SAVED_CONTEXT_FILENAME, mode="w") as f:
            pickle.dump(context, f)
        print(f"Context is saved, and used as test_context from next time in auto test."
              f"Starting to run {self.test_func.__name__} with the context.")
        await self.test_func(context)

    def load_context(self):
        with open(self.SAVED_CONTEXT_FILENAME, mode="r") as f:
            ctx = pickle.load(f)
        return ctx
