# jsb/drivers/tornado/bot.py
#
#

""" tornado web bot. """

# jsb imports

import copy
import functools
import logging
import time

from jsb.imports import getjson
from jsb.lib.botbase import BotBase
from jsb.lib.channelbase import ChannelBase
from jsb.lib.container import Container
from jsb.lib.eventbase import EventBase
from jsb.lib.outputcache import add
from jsb.utils.exception import handle_exception
from jsb.utils.generic import fromenc, stripcolor, strippedtxt, toenc
from jsb.utils.timeutils import hourmin
from jsb.utils.url import re_url_match

import tornado.ioloop
import tornado.web

json = getjson()

# basic imports


# tornado import


# defines

cpy = copy.deepcopy

# WebBot class


class TornadoBot(BotBase):

    """TornadoBot  just inherits from botbase for now."""

    def __init__(
        self, cfg=None, users=None, plugs=None, botname="tornado-bot", *args, **kwargs
    ):
        BotBase.__init__(
            self, cfg, users, plugs, botname, bottype="tornado", *args, **kwargs
        )
        assert self.cfg
        self.cfg.type = "tornado"
        self.isgae = False
        self.websockets = {}

    def _raw(self, txt, target=None, how="normal", handler=None, end=""):
        """put txt to the client."""
        logging.warn("> %s (%s)" % (txt, self.cfg.name))
        if not txt:
            return
        txt = txt + end
        if handler:
            handler.write(txt)
        else:
            print(txt)

    def outnocb(
        self,
        channel,
        txt,
        how=None,
        event=None,
        origin=None,
        response=None,
        dotime=False,
        *args,
        **kwargs
    ):
        txt = self.normalize(txt)
        if event and event.how != "background":
            logging.info("%s - out - %s" % (self.cfg.name, txt))
        if "http://" in txt or "https://" in txt:
            for item in re_url_match.findall(txt):
                logging.debug("web - raw - found url - %s" % item)
                url = (
                    '<a href="%s" onclick="window.open(\'%s\'); return false;">%s</a>'
                    % (item, item, item)
                )
                try:
                    txt = txt.replace(item, url)
                except ValueError:
                    logging.error("web - invalid url - %s" % url)
        if response or (event and event.doweb):
            self._raw(txt, event.target, event.how, event.handler)
        else:
            if event:
                e = cpy(event)
                e.txt = txt
                e.channel = channel
                e.how = event.how or how
            else:
                e = EventBase()
                e.nick = self.cfg.nick
                e.userhost = self.cfg.nick + "@" + "bot"
                e.channel = channel
                e.txt = txt
                e.div = "content_div"
                e.origin = origin
                e.how = how or "overwrite"
                e.headlines = True
            e.update(kwargs)
            update_web(self, e)
        self.benice(event)

    def normalize(self, txt):
        txt = stripcolor(txt)
        txt = txt.replace("\n", "<br>")
        txt = txt.replace("<", "&lt;")
        txt = txt.replace(">", "&gt;")
        txt = strippedtxt(txt)
        txt = txt.replace("&lt;br&gt;", "<br>")
        txt = txt.replace("&lt;b&gt;", "<b>")
        txt = txt.replace("&lt;/b&gt;", "</b>")
        txt = txt.replace("&lt;i&gt;", "<i>")
        txt = txt.replace("&lt;/i&gt;", "</i>")
        txt = txt.replace("&lt;h2&gt;", "<h2>")
        txt = txt.replace("&lt;/h2&gt;", "</h2>")
        txt = txt.replace("&lt;h3&gt;", "<h3>")
        txt = txt.replace("&lt;/h3&gt;", "</h3>")
        txt = txt.replace("&lt;li&gt;", "<li>")
        txt = txt.replace("&lt;/li&gt;", "</li>")
        return txt

    def reconnect(self, *args):
        return True


def update_web(bot, event, end="<br>"):
    out = Container(event.userhost, event.tojson(), how="tornado").tojson()
    logging.warn("> %s - %s" % (event.userhost, event.txt))
    logging.debug("> %s" % out)
    if event.channel not in bot.websockets:
        logging.info("no %s in websockets dict" % event.channel)
        return
    for c in bot.websockets[event.channel]:
        time.sleep(0.001)
        try:
            callback = functools.partial(c.write_message, out)
            bot.server.io_loop.add_callback(callback)
        except IOError as ex:
            logging.error("IOError occured: %s" % str(ex))
            raise
