# import test import auto_run
import test

from messaging import SplitMessanger


async def test_split(channel):
    msgr = SplitMessanger(channel, "first", joint="\n")
    for _ in range(100):
        msgr += "0123456789"
        msgr += "あいうえおかきくけこさしすせそ"
    await msgr.send()


test.suites.append(test_split)
test.auto_run()
