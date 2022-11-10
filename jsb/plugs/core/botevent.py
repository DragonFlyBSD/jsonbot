# jsb/plugs/core/botevent.py
#
#

""" provide handling of host/tasks/botevent tasks. """

# jsb imports

import logging

from jsb.imports import getjson
from jsb.lib.botbase import BotBase
from jsb.lib.callbacks import callbacks, first_callbacks, last_callbacks
from jsb.lib.eventbase import EventBase
from jsb.lib.factory import BotFactory
from jsb.lib.tasks import taskmanager
from jsb.utils.exception import handle_exception
from jsb.utils.lazydict import LazyDict

# simplejson imports


json = getjson()

# basic imports


# boteventcb callback


def boteventcb(inputdict, request, response):
    # logging.warn(inputdict)
    # logging.warn(dir(request))
    # logging.warn(dir(response))
    body = request.body
    # logging.warn(body)
    payload = json.loads(body)
    try:
        botjson = payload["bot"]
        logging.warn(botjson)
        cfg = LazyDict(json.loads(botjson))
        # logging.warn(str(cfg))
        bot = BotFactory().create(cfg.type, cfg)
        logging.warn("created bot: %s" % bot.tojson(full=True))
        eventjson = payload["event"]
        # logging.warn(eventjson)
        event = EventBase()
        event.update(LazyDict(json.loads(eventjson)))
        logging.warn("created event: %s" % event.tojson(full=True))
        event.notask = True
        bot.doevent(event)
    except Exception as ex:
        handle_exception()


taskmanager.add("botevent", boteventcb)
