# jsb/plugs/core/remotecallbacks.py
#
#

""" dispatch remote events. """
raise ImportError(
    "This module requires xmlstream which is not supported for python3. If you wish to use it, please rewrite the code to use a different XML library"
)
# jsb imports

import copy
import hashlib
import hmac
import logging

from jsb.lib.callbacks import callbacks, first_callbacks, remote_callbacks
from jsb.lib.commands import cmnds
from jsb.lib.container import Container
from jsb.lib.errors import NoProperDigest
from jsb.lib.eventbase import EventBase
from jsb.lib.examples import examples
from jsb.utils.exception import handle_exception
from jsb.utils.generic import fromenc
from jsb.utils.lazydict import LazyDict
from xmlstream import NodeBuilder, XMLescape, XMLunescape

# basic imports


# defines

cpy = copy.deepcopy

# callback


def remotecb(bot, event):
    """dispatch an event."""
    try:
        container = Container().load(event.txt)
    except TypeError:
        handle_exception()
        logging.warn("remotecallbacks - not a remote event - %s " % event.userhost)
        return
    logging.debug("doing REMOTE callback")
    try:
        digest = hmac.new(
            str(container.hashkey), XMLunescape(container.payload), hashlib.sha512
        ).hexdigest()
        logging.debug("remotecallbacks - digest is %s" % digest)
    except TypeError:
        handle_exception()
        logging.error("remotecallbacks - can't load payload - %s" % container.payload)
        return
    if container.digest == digest:
        e = EventBase().load(XMLunescape(container.payload))
    else:
        raise NoProperDigest()
    e.txt = XMLunescape(e.txt)
    e.nodispatch = True
    e.forwarded = True
    e.dontbind = True
    bot.doevent(e)
    event.status = "done"
    return


remote_callbacks.add("MESSAGE", remotecb)
