# jsb/plugs/core/size.py
#
#

""" call a size() function in every module in sys.modules """

# jsb imports

import sys

from jsb.lib.commands import cmnds
from jsb.lib.examples import examples
from jsb.utils.exception import handle_exception

# basic imports


# size command


def handle_size(bot, event):
    res = []
    mods = dict(sys.modules)
    for name, mod in mods.items():
        if not "jsb" in name:
            continue
        try:
            res.append(
                "<i><%s></i> %s" % (name.split(".")[-1], str(getattr(mod, "size")()))
            )
        except (TypeError, AttributeError):
            continue
        except Exception as ex:
            handle_exception()
    event.reply("sizes in %s modules scanned: " % len(res), res, dot=", ")


cmnds.add("size", handle_size, "OPER")
examples.add("size", "call size() functions in all available modules", "size")
