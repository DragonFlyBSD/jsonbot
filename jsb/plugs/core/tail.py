# jsb/plugs/core/tail.py
#
#

""" tail bot results. """

# jsb imports

import time

from jsb.lib.commands import cmnds
from jsb.lib.examples import examples
from jsb.utils.generic import waitforqueue

# basic imports


# tail command


def handle_tail(bot, ievent):
    """no arguments - show last <nr> elements, use this command in a pipeline."""
    try:
        nr = int(ievent.args[0])
    except (ValueError, IndexError):
        nr = 3
    if not ievent.inqueue:
        time.sleep(0.5)
    ievent.reply("results: ", list(ievent.inqueue)[-nr:])


cmnds.add("tail", handle_tail, ["OPER", "USER", "GUEST"])
examples.add("tail", "show last <nr> lines of pipeline output", "list ! tail 5")
