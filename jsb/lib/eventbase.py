# jsb/lib/eventbase.py
#
#

""" base class of all events.  """

## jsb imports

from channelbase import ChannelBase
from jsb.utils.lazydict import LazyDict
from jsb.utils.generic import splittxt, stripped, waitforqueue
from errors import NoSuchUser, NoSuchCommand, RequireError
from jsb.utils.opts import makeeventopts
from jsb.utils.trace import whichmodule
from jsb.utils.exception import handle_exception
from jsb.utils.locking import lockdec
from jsb.lib.config import Config, getmainconfig
from jsb.lib.users import getusers
from jsb.lib.commands import cmnds
from jsb.lib.floodcontrol import floodcontrol

## basic imports

from collections import deque
from xml.sax.saxutils import unescape
import copy
import logging
import Queue
import types
import socket
import threading
import time
import thread
import urllib
import uuid

## defines

cpy = copy.deepcopy
lock = thread.allocate_lock()
locked = lockdec(lock)

## classes

class EventBase(LazyDict):

    """ basic event class. """

    def __init__(self, input={}, bot=None):
        LazyDict.__init__(self)
        if bot: self.bot = bot
        self.ctime = time.time()
        self.speed = self.speed or 5
        self.nrout = self.nrout or 0
        if input: self.copyin(input)
        if not self.token: self.setup()

    def copyin(self, eventin):
        """ copy in an event. """
        self.update(eventin)
        return self

    def setup(self):
        self.token = self.token or str(uuid.uuid4().hex)
        self.finished = threading.Condition()
        self.busy = deque()
        self.inqueue = deque()
        self.outqueue = deque()
        self.resqueue = deque()
        self.ok = threading.Event()
        return self

    def __deepcopy__(self, a):
        """ deepcopy an event. """
        e = EventBase(self)
        return e

    def launched(self):
        logging.info(str(self))
        self.ok.set()

    def startout(self):
        if not self.nodispatch and not self.token in self.busy: self.busy.append(self.token)

    def ready(self, what=None, force=False):
        """ signal the event as ready - push None to all queues. """
        if self.nodispatch: return
        if not "TICK" in self.cbtype: logging.info(self.busy)
        try: self.busy.remove(self.token)
        except ValueError: pass
        if not self.busy or force: self.notify()
         
    def notify(self, p=None):
        self.finished.acquire()
        self.finished.notifyAll()
        self.finished.release()
        if not "TICK" in self.cbtype: logging.info("notified %s" % str(self))

    def execwait(self, direct=False):
        from jsb.lib.commands import cmnds
        e = self.bot.put(self)
        if e: return e.wait()
        else: logging.info("no response for %s" % self.txt) ; return
        logging.info("%s wont dispatch" % self.txt)

    def wait(self, nr=1000):
        nr = int(nr)
        result = []
        #if self.nodispatch: return
        if not self.busy: self.startout()
        self.finished.acquire()
        while nr > 0 and (self.busy and not self.dostop): self.finished.wait(0.1) ; nr -= 100
        self.finished.release()
        if self.wait and self.thread: logging.warn("joining thread %s" % self.thread) ; self.thread.join(nr/1000)
        if not "TICK" in self.cbtype: logging.info(self.busy)
        if not self.resqueue: res = waitforqueue(self.resqueue, nr)
        else: res = self.resqueue
        return list(res)

    def waitandout(self, nr=1000):
        res = self.wait(nr)
        if res: 
            for r in res: self.reply(r)

    def execute(self, direct=False, *args, **kwargs):
        """ dispatch event onto the cmnds object. this method needs both event.nodispatch = False amd event.iscommand = True set. """
        logging.debug("execute %s" % self.cbtype)
        from jsb.lib.commands import cmnds
        res = self
        self.startout()
        self.bind(self.bot, force=True, dolog=True)
        if not self.pipelined and ' ! ' in self.txt: res = self.dopipe(direct, *args, **kwargs)
        else:
            try: res = cmnds.dispatch(self.bot, self, direct=direct, *args, **kwargs)
            except RequireError, ex: logging.error(str(ex))
            except NoSuchCommand, ex: logging.error("we don't have a %s command" % str(ex))
            except NoSuchUser, ex: logging.error("we don't have user for %s" % str(ex))
            except Exception , ex: handle_exception()
        return res

    def dopipe(self, direct=False, *args, **kwargs):
        """ split cmnds, create events for them, chain the queues and dispatch.  """
        direct = True
        logging.warn("starting pipeline")
        origout = self.outqueue
        events = []
        self.pipelined = True
        splitted = self.txt.split(" ! ")
        for i in range(len(splitted)):
            t = splitted[i].strip()
            if not t: continue
            if t[0] != ";": t = ";" + t
            e = self.bot.make_event(self.userhost, self.channel, t)
            e.outqueue = deque()
            e.busy = deque()
            e.prev = None
            e.pipelined = True
            e.dontbind = False
            if not e.woulddispatch(): raise NoSuchCommand(e.txt)
            events.append(e)
        prev = None
        for i in range(len(events)):
            if i > 0:
                events[i].inqueue = events[i-1].outqueue
                events[i].prev = events[i-1]
        events[-1].pipelined = False
        events[-1].dontclose = False
        for i in range(len(events)):
            if not self.bot.isgae and not direct: self.bot.put(events[i])
            else: events[i].execute(direct)
        return events[-1]

    def prepare(self, bot=None):
        """ prepare the event for dispatch. """
        if bot: self.bot = bot or self.bot
        assert(self.bot)
        self.origin = self.channel
        self.bloh()
        self.makeargs()
        if not self.nolog: logging.debug("%s - prepared event - %s" % (self.auth, self.cbtype))
        return self

    def bind(self, bot=None, user=None, chan=None, force=False, dolog=None):
        """ bind event.bot event.user and event.chan to execute a command on it. """
        #if self.nodispatch: logging.debug("nodispatch is set on event . .not binding"); return
        dolog = dolog or 'TICK' not in self.cbtype
        if dolog and not force and self.dontbind: logging.debug("dontbind is set on event . .not binding"); return
        if not force and self.bonded and (bot and not bot.isgae): logging.debug("already bonded") ; return
        dolog and logging.debug("starting bind on %s - %s" % (self.userhost, self.txt)) 
        target = self.auth or self.userhost
        bot = bot or self.bot
        if not self.chan:
            if chan: self.chan = chan
            elif self.channel: self.chan = ChannelBase(self.channel, bot.cfg.name)
            elif self.userhost: self.chan = ChannelBase(self.userhost, bot.cfg.name)
            if self.chan:
                #self.debug = self.chan.data.debug or False
                dolog and logging.debug("channel bonded - %s" % self.chan.data.id)
        self.prepare(bot)
        if not target: self.bonded = True ; return
        if not self.user and target and not self.nodispatch:
            if user: u = user
            else: u = bot.users.getuser(target)
            if not u: 
                cfg = getmainconfig()
                if cfg.auto_register and self.iscommand:
                    u = bot.users.addguest(target, self.nick)
                    if u: logging.warn("auto_register applied")
                    else: logging.error("can't add %s to users database" % target)
            if u:
                msg = "!! %s -=- %s -=- %s -=- (%s) !!" % (u.data.name, self.usercmnd or "none", self.cbtype, self.bot.cfg.name)
                dolog and logging.warn(msg)
                self.user = u
            if self.user: dolog and logging.debug("user bonded from %s" % whichmodule())
        if not self.user and target: dolog and self.iscommand and logging.warn("no %s user found" % target) ; self.nodispatch = True
        if self.bot: self.inchan = self.channel in self.bot.state.data.joinedchannels
        self.bonded = True
        return self

    def bloh(self, bot=None, *args, **kwargs):
        """ overload this. """
        if not self.txt: return
        self.bot = bot or self.bot
        self.execstr = self.iscmnd()
        if self.execstr:
            self.usercmnd = self.execstr.split()[0]
            self.nodispatch = False
            self.iscommand = True
        else: logging.debug("can't detect a command on %s (%s)" % (self.txt, self.cbtype))
     
    def reply(self, txt, result=[], event=None, origin="", dot=u", ", nr=375, extend=0, showall=False, *args, **kwargs):
        """ reply to this event """
        try: target = self.channel or self.arguments[1]
        except (IndexError, TypeError): target = self.channel or "nochannel"
        if self.silent:
            self.msg = True
            self.bot.say(self.nick, txt, result, self.userhost, extend=extend, event=self, dot=dot, nr=nr, showall=showall, *args, **kwargs)
        elif self.isdcc: self.bot.say(self.sock, txt, result, self.userhost, extend=extend, event=self, dot=dot, nr=nr, showall=showall, *args, **kwargs)
        else: self.bot.say(target, txt, result, self.userhost, extend=extend, event=self, dot=dot, nr=nr, showall=showall, *args, **kwargs)
        return self

    def missing(self, txt):
        """ display missing arguments. """
        if self.alias: l = len(self.alias.split()) - 1
        else: l = 0
        t = ' '.join(txt.split()[l:])
        self.reply("%s %s" % (self.aliased or self.usercmnd, t), event=self) 
        return self

    def done(self):
        """ tell the user we are done. """
        self.reply('<b>done</b> - %s' % (self.usercmnd or self.alias or selt.txt), event=self)
        return self

    def leave(self):
        """ lower the time to leave. """
        self.ttl -= 1
        if self.ttl <= 0 : self.status = "done"

    def makeoptions(self):
        """ check the given txt for options. """
        try: self.options = makeeventopts(self.txt)
        except: handle_exception() ; return 
        if not self.options: return
        if self.options.channel: self.target = self.options.channel
        logging.debug("options - %s" % unicode(self.options))
        self.txt = ' '.join(self.options.args)
        self.makeargs()

    def makeargs(self):
        """ make arguments and rest attributes from self.txt. """
        if not self.execstr:
            self.args = []
            self.rest = ""
        else:
            args = self.execstr.split()
            self.chantag = args[0]
            if len(args) > 1:
                self.args = args[1:]
                self.rest = ' '.join(self.args)
            else:
                self.args = []
                self.rest = ""

    def makeresponse(self, txt, result, dot=u", ", *args, **kwargs):
        """ create a response from a string and result list. """
        return self.bot.makeresponse(txt, result, dot, *args, **kwargs)

    def less(self, what, nr=365):
        """ split up in parts of <nr> chars overflowing on word boundaries. """
        return self.bot.less(what, nr)

    def isremote(self):
        """ check whether the event is off remote origin. """
        return self.txt.startswith('{"') or self.txt.startswith("{&")

    def iscmnd(self):
        """ check if event is a command. """
        if not self.txt: return ""
        if not self.bot: return ""
        if self.txt[0] in self.getcc(): return self.txt[1:]
        matchnick = unicode(self.bot.cfg.nick + u":")
        if self.txt.startswith(matchnick): return self.txt[len(matchnick):]
        matchnick = unicode(self.bot.cfg.nick + u",")
        if self.txt.startswith(matchnick): return self.txt[len(matchnick):]
        if self.iscommand and self.execstr: return self.execstr
        return ""

    hascc = stripcc = iscmnd

    def gotcc(self):
        if not self.txt: return False
        return self.txt[0] in self.getcc()

    def getcc(self):
        if self.chan: cc = self.chan.data.cc
        else: cc = ""
        if not cc:
            cfg = getmainconfig()
            if cfg.globalcc and not cfg.globalcc in cc: cc += cfg.globalcc
        if not cc: cc = "!;"
        if not ";" in cc: cc += ";"
        logging.info("cc is %s" % cc)
        return cc

    def blocked(self):
        return floodcontrol.checkevent(self)

    def woulddispatch(self):
        cmnds.reloadcheck(self.bot, self)
        return cmnds.woulddispatch(self.bot, self)

    def wouldmatchre(self):
        return cmnds.wouldmatchre(self.bot, self)
