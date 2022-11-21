# jsb/console/event.py
#
#

""" a console event. """

# jsb imports

import getpass

from jsb.lib.channelbase import ChannelBase
from jsb.lib.errors import NoInput
from jsb.lib.eventbase import EventBase

# basic imports


# ConsoleEvent class


class ConsoleEvent(EventBase):
    def parse(self, bot, input, console, *args, **kwargs):
        """overload this."""
        if not input:
            raise NoInput()
        self.bot = bot
        self.console = console
        self.nick = getpass.getuser()
        self.auth = self.nick + "@" + bot.cfg.uuid
        self.userhost = self.auth
        self.origin = self.userhost
        self.txt = input
        self.channel = self.userhost
        self.cbtype = self.cmnd = "CONSOLE"
        self.showall = True
        self.prepare()
        return self
