# jsb/api/__init__.py
#
#

""" JSONBOT package for the REST API. """

__version__ = "0.1"

import logging
import urllib.error
import urllib.parse
import urllib.request

from jsb.lib.callbacks import api_callbacks


class APIHooks(object):
    def __init__(self):
        self.cbs = {}

    def register(self, path, handler):
        logging.warn("%s - %s" % (path, str(handler)))
        self.cbs[path] = handler

    def unregister(self, path):
        logging.warn(path)
        del self.cbs[path]

    def dispatch(self, urlpath, bot, event):
        urlpath = urllib.parse.unquote_plus(urlpath.strip())
        urlpath = urlpath.split("#")[0]
        urlpath = urlpath.split("?")[0]
        for path, cb in self.cbs.items():
            if path == urlpath:
                cb(bot, event)
                return


get_hooks = APIHooks()
post_hooks = APIHooks()


def api_check(bot, event):
    if event.apitype == "POST":
        post_hooks.dispatch(event.upath, bot, event)
    elif event.apitype == "GET":
        get_hooks.dispatch(event.upath, bot, event)
    else:
        logging.error("unknown api type %s" % event.apitype)


def api_ping(bot, event):
    event.reply("pong")


get_hooks.register("ping", api_ping)
