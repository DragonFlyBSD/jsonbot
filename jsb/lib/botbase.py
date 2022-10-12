# jsb/botbase.py
#
#

""" base class for all bots. """

## jsb imports

from jsb.utils.exception import handle_exception
from runner import defaultrunner, callbackrunner, waitrunner
from eventhandler import mainhandler
from jsb.utils.lazydict import LazyDict
from plugins import plugs as coreplugs
from callbacks import callbacks, first_callbacks, last_callbacks, remote_callbacks
from eventbase import EventBase
from errors import NoSuchCommand, PlugsNotConnected, NoOwnerSet, NameNotSet, NoEventProvided
from commands import Commands, cmnds
from config import Config, getmainconfig
from jsb.utils.pdod import Pdod
from channelbase import ChannelBase
from less import Less, outcache
from boot import boot, getcmndperms, default_plugins
from jsb.utils.locking import lockdec
from exit import globalshutdown
from jsb.utils.generic import splittxt, toenc, fromenc, waitforqueue, strippedtxt, waitevents, stripcolor
from jsb.utils.trace import whichmodule
from fleet import getfleet
from aliases import getaliases
from jsb.utils.name import stripname
from tick import tickloop
from threads import start_new_thread, threaded
from morphs import inputmorphs, outputmorphs
from gatekeeper import GateKeeper
from wait import waiter
from factory import bot_factory
from jsb.lib.threads import threaded
from jsb.utils.locking import lock_object, release_object
from jsb.utils.url import decode_html_entities
from jsb.lib.users import getusers

try: import wave
except ImportError:
    from jsb.imports import gettornado
    tornado = gettornado()
    import tornado.ioloop

## basic imports

import time
import logging
import copy
import sys
import getpass
import os
import thread
import types
import threading
import Queue
import re
import urllib
from collections import deque

## defines

cpy = copy.deepcopy

## locks

reconnectlock = threading.RLock()
reconnectlocked = lockdec(reconnectlock)

lock = thread.allocate_lock()
locked = lockdec(lock)

## classes

class BotBase(LazyDict):

    """ base class for all bots. """

    def __init__(self, cfg=None, usersin=None, plugs=None, botname=None, nick=None, bottype=None, *args, **kwargs):
        logging.debug("type is %s" % str(type(self)))
        if cfg: self.cfg = cfg ; botname = botname or self.cfg.name
        if not botname: botname = u"default-%s" % str(type(self)).split('.')[-1][:-2]
        if not botname: raise Exception("can't determine  botname")
        self.fleetdir = u'fleet' + os.sep + stripname(botname)
        if not self.cfg: self.cfg = Config(self.fleetdir + os.sep + u'config')
        self.cfg.name = botname or self.cfg.name
        if not self.cfg.name: raise Exception("name is not set in %s config file" % self.fleetdir)
        logging.debug("name is %s" % self.cfg.name)
        LazyDict.__init__(self)
        logging.debug("created bot with config %s" % self.cfg.tojson(full=True))
        self.ecounter = 0
        self.ignore = []
        self.ids = []
        self.aliases = getaliases()
        self.reconnectcount = 0
        self.plugs = coreplugs
        self.gatekeeper = GateKeeper(self.cfg.name)
        self.gatekeeper.allow(self.user or self.jid or self.cfg.server or self.cfg.name)
        try:
            import waveapi
            self.isgae = True
            logging.debug("bot is a GAE bot (%s)" % self.cfg.name)
        except ImportError:
            self.isgae = False
            logging.debug("bot is a shell bot (%s)" % self.cfg.name)
        self.starttime = time.time()
        self.type = bottype or "base"
        self.status = "init"
        self.networkname = self.cfg.networkname or self.cfg.name or ""
        from jsb.lib.datadir import getdatadir
        datadir = getdatadir()
        self.datadir = datadir + os.sep + self.fleetdir
        self.maincfg = getmainconfig()
        self.owner = self.cfg.owner
        if not self.owner:
            logging.debug(u"owner is not set in %s - using mainconfig" % self.cfg.cfile)
            self.owner = self.maincfg.owner
        self.users = usersin or getusers()
        logging.debug(u"owner is %s" % self.owner)
        self.users.make_owner(self.owner)
        self.outcache = outcache
        self.userhosts = LazyDict()
        self.nicks = LazyDict()
        self.connectok = threading.Event()
        self.reconnectcount = 0
        self.cfg.nick = nick or self.cfg.nick or u'jsb'
        try:
            if not os.isdir(self.datadir): os.mkdir(self.datadir)
        except: pass
        self.setstate()
        self.outputlock = thread.allocate_lock()
        try:
            self.outqueue = Queue.PriorityQueue()
            self.eventqueue = Queue.PriorityQueue()
        except AttributeError:
            self.outqueue = Queue.Queue()
            self.eventqueue = Queue.Queue()
        self.encoding = self.cfg.encoding or "utf-8"
        self.cmndperms = getcmndperms()
        self.outputmorphs = outputmorphs
        self.inputmorphs = inputmorphs
        if not self.isgae: tickloop.start(self)

    def copyin(self, data):
        self.update(data)

    def _resume(self, data, botname, *args, **kwargs):
        pass

    def _resumedata(self):
        """ return data needed for resuming. """
        try: self.cfg.fd = self.oldsock.fileno()
        except AttributeError: logging.warn("no oldsock found for %s" % self.cfg.name)
        return {self.cfg.name: dict(self.cfg)}

    def benice(self, event=None, sleep=0.005):
        if self.server and self.server.io_loop:
            logging.debug("i'm being nice")
            if event and self.server and event.handler: self.server.io_loop.add_callback(event.handler.async_callback(lambda: time.sleep(sleep)))
            elif self.server: self.server.io_loop.add_callback(lambda: time.sleep(sleep))
        time.sleep(sleep)

    def do_enable(self, modname):
        """ enable plugin given its modulename. """
        try: self.cfg.blacklist and self.cfg.blacklist.remove(modname)
        except ValueError: pass           
        if self.cfg.loadlist and modname not in self.cfg.loadlist: self.cfg.loadlist.append(modname)
        self.cfg.save()

    def do_disable(self, modname):
        """ disable plugin given its modulename. """
        if self.cfg.blacklist and modname not in self.cfg.blacklist: self.cfg.blacklist.append(modname)
        if self.cfg.loadlist and modname in self.cfg.loadlist: self.cfg.loadlist.remove(modname)
        self.cfg.save()

    #@locked
    def put(self, event, direct=False):
        """ put an event on the worker queue. """
        if direct: self.doevent(event)
        elif self.isgae:
            from jsb.drivers.gae.tasks import start_botevent
            start_botevent(self, event, event.speed)
        else:
            if event:
                 logging.debug("putted event on %s" % self.cfg.name)
                 self.ecounter += 1
                 self.input(event.speed, event)
            else: self.input(0, None)
        return event

    def broadcast(self, txt):
        """ broadcast txt to all joined channels. """
        for chan in self.state['joinedchannels']:
            self.say(chan, txt)

    def _eventloop(self):
        """ output loop. """
        logging.debug('%s - starting eventloop' % self.cfg.name)
        self.stopeventloop = 0
        while not self.stopped and not self.stopeventloop:
            try:
                res = self.eventqueue.get()
                if not res: break
                (prio, event) = res
                if not event: break
                logging.debug("%s - eventloop - %s - %s" % (self.cfg.name, event.cbtype, event.userhost)) 
                event.speed = prio
                self.doevent(event)
                self.benice()
            except Queue.Empty: time.sleep(0.01) ; continue
            except Exception, ex: handle_exception() ; logging.warn("error in eventloop: %s" % str(ex))
        logging.debug('%s - stopping eventloop' % self.cfg.name)

    def input(self, prio, event):
        """ put output onto one of the output queues. """
        self.eventqueue.put(("%s-%s" % (prio, self.ecounter), event))

    def _outloop(self):
        """ output loop. """
        logging.debug('%s - starting output loop' % self.cfg.name)
        self.stopoutloop = 0
        while not self.stopped and not self.stopoutloop:
            try:
                r = self.outqueue.get() 
                if not r: continue
                (prio, res) = r
                logging.debug("%s - OUT - %s - %s" % (self.cfg.name, self.type, str(res))) 
                if not res: continue
                self.out(*res)
            except Queue.Empty: time.sleep(0.1) ; continue
            except Exception, ex: handle_exception()
        logging.debug('%s - stopping output loop' % self.cfg.name)

    def _pingloop(self):
        """ output loop. """
        logging.debug('%s - starting ping loop' % self.cfg.name)
        time.sleep(5)
        while not self.stopped:
            try:
                if self.status != "start" and not self.pingcheck(): self.reconnect() ; break
            except Exception, ex: logging.error(str(ex)) ; self.reconnect() ; break
            time.sleep(self.cfg.pingsleep or 60)
        logging.debug('%s - stopping ping loop' % self.cfg.name)

    def putonqueue(self, nr, *args):
        """ put output onto one of the output queues. """
        self.outqueue.put((nr, args))

    def outputsizes(self):
        """ return sizes of output queues. """
        return (self.outqueue.qsize(), self.eventqueue.qsize())

    def setstate(self, state=None):
        """ set state on the bot. """
        self.state = state or Pdod(self.datadir + os.sep + 'state')
        if self.state and not 'joinedchannels' in self.state.data: self.state.data.joinedchannels = []

    def setusers(self, users=None):
        """ set users on the bot. """
        if users:
            self.users = users
            return
        import jsb.lib.users as u
        if not u.users: u.users_boot()
        self.users = u.users

    def loadplugs(self, packagelist=[]):
        """ load plugins from packagelist. """
        self.plugs.loadall(packagelist)
        return self.plugs

    def joinchannels(self):
        """ join channels. """
        time.sleep(getmainconfig().waitforjoin or 1)
        target = self.cfg.channels
        try:
            for i in self.state['joinedchannels']:
                if i not in target: target.append(i)
        except: pass
        if not target: target = self.state['joinedchannels']
        for i in target:
            try:
                logging.debug("%s - joining %s" % (self.cfg.name, i))
                channel = ChannelBase(i, self.cfg.name)
                if channel: key = channel.data.key
                else: key = None
                if channel.data.nick: self.ids.append("%s/%s" % (i, channel.data.nick))
                start_new_thread(self.join, (i, key))
            except Exception, ex:
                logging.warn('%s - failed to join %s: %s' % (self.cfg.name, i, str(ex)))
                handle_exception()
            time.sleep(3)

    def boot(self):
        logging.warn("booting %s bot" % self.cfg.name)
        if not self.cfg.type: self.cfg.type = self.type ; self.cfg.save()
        fleet = getfleet()
        fleet.addbot(self)
        fleet.addnametype(self.cfg.name, self.type)
        while 1:
            try:
                #self.exit(close=False, save=False)
                self.started = False
                if self.start(): break
            except Exception, ex:
                logging.error(str(ex))
                logging.error("sleeping 15 seconds")
                time.sleep(15)       

    def start(self, connect=True, join=True):
        """ start the mainloop of the bot. """
        if self.started: logging.warn("%s - already started" % self.cfg.name) ; return
        self.stopped = False
        self.stopreadloop = False
        self.stopoutloop = False
        self.status = "start"
        if not self.isgae:
            start_new_thread(self._eventloop, ())
            if connect:
                if not self.connect() : return False
                start_new_thread(self._readloop, ())
                start_new_thread(self._outloop, ())
                self.connectok.wait()
                if self.stopped: logging.warn("bot is stopped") ; return True
                if self.connectok.isSet():
                    logging.warn('%s - logged on !' % self.cfg.name)
                    if join: start_new_thread(self.joinchannels, ())
                elif self.type not in ["console", "base"]: logging.warn("%s - failed to logon - connectok is not set" % self.cfg.name)
        self.status == "started"
        self.started = True
        self.dostart(self.cfg.name, self.type)
        return True

    def doremote(self, event):
        """ dispatch an event. """
        if not event: raise NoEventProvided()
        event.nodispatch = True
        event.forwarded = True
        event.dontbind = True
        event.prepare(self)
        self.status = "callback"
        starttime = time.time()
        msg = "%s - %s - %s - %s" % (self.cfg.name, event.auth, event.how, event.cbtype)
        logging.warn(msg)
        try: logging.debug("remote - %s" % event.dump())
        except: pass
        if self.closed:
            if self.gatekeeper.isblocked(event.origin): return
        if event.status == "done":
            logging.debug("%s - event is done .. ignoring" % self.cfg.name)
            return
        e0 = cpy(event)
        e0.speed = 1
        remote_callbacks.check(self, e0)
        return

    def doevent(self, event):
        """ dispatch an event. """ 
        time.sleep(0.01)
        if not self.cfg: raise Exception("eventbase - cfg is not set .. can't handle event.") ; return
        if not event: raise NoEventProvided()
        self.ecounter += 1
        try:
            if event.isremote(): self.doremote(event) ; return
            if event.type == "groupchat" and event.fromm in self.ids:
                logging.debug("%s - receiving groupchat from self (%s)" % (self.cfg.name, event.fromm))
                return
            event.txt = self.inputmorphs.do(fromenc(event.txt, self.encoding), event)
        except UnicodeDecodeError: logging.warn("%s - got decode error in input .. ingoring" % self.cfg.name) ; return
        event.bind(self)
        try: logging.debug("%s - event dump: %s" % (self.cfg.name, event.dump()))
        except: pass
        self.status = "callback"
        starttime = time.time()
        if self.closed:
            if self.gatekeeper.isblocked(event.origin): return
        if event.status == "done":
            logging.debug("%s - event is done .. ignoring" % self.cfg.name)
            return
        if event.msg or event.isdcc: event.speed = 2
        e1 = cpy(event)
        first_callbacks.check(self, e1)
        if not e1.stop: 
            callbacks.check(self, e1)
            if not e1.stop: last_callbacks.check(self, e1)
        event.callbackdone = True
        waiter.check(self, event)
        return event

    def ownercheck(self, userhost):
        """ check if provided userhost belongs to an owner. """
        if self.cfg and self.cfg.owner:
            if userhost in self.cfg.owner: return True
        logging.warn("failed ownercheck for %s" % userhost)
        return False

    def exit(self, stop=True, close=True, save=True, quit=False):
        """ exit the bot. """ 
        logging.warn("%s - exit" % self.cfg.name)
        if stop:
            self.stopped = True   
            self.stopreadloop = True  
            self.connected = False
            self.started = False
        if close:
            self.putonqueue(1, None, "")
            self.put(None)
            self.shutdown()
        save and self.save()
        fleet = getfleet()
        fleet.remove(self)
        if quit and not fleet.bots: globalshutdown()
        
    def _raw(self, txt, *args, **kwargs):
        """ override this. outnocb() is used more though. """ 
        logging.debug(u"%s - out - %s" % (self.cfg.name, txt))
        print txt

    def makeoutput(self, printto, txt, result=[], nr=375, extend=0, dot=", ", origin=None, showall=False, *args, **kwargs):
        """ chop output in pieces and stored it for !more command. """
        if not txt: return ""
        txt = self.makeresponse(txt, result, dot)
        if showall: return txt
        res1, nritems = self.less(origin or printto, txt, nr+extend)
        return res1

    def out(self, printto, txt, how="msg", event=None, origin=None, *args, **kwargs):
        """ output method with OUTPUT event generated. """
        self.outmonitor(origin, printto, txt, event=event)
        self.outnocb(printto, txt, how, event=event, origin=origin, *args, **kwargs)
        if event: event.ready()

    write = out

    def outnocb(self, printto, txt, how="msg", event=None, origin=None, *args, **kwargs):
        """ output function without callbacks called.. override this in your driver. """
        self._raw(txt)

    writenocb = outnocb

    def say(self, channel, txt, result=[], how="msg", event=None, nr=375, extend=0, dot=", ", showall=False, *args, **kwargs):
        """ default method to send txt from the bot to a user/channel/jid/conference etc. """
        logging.warn("saying to %s" % channel)
        if event:
            #event.busy.append(event.usercmnd)
            if event.userhost in self.ignore: logging.warn("%s - ignore on %s - no output done" % (self.cfg.name, event.userhost)) ; return
            if event.how == "msg" and self.type == "irc": target = event.nick
            else: target = channel
            if event.pipelined:
                for i in result: event.outqueue.append(i)
                return
        else: target = channel
        if showall or (event and event.showall): txt = self.makeresponse(txt, result, dot, *args, **kwargs)
        else: txt = self.makeoutput(channel, txt, result, nr, extend, dot, origin=target, *args, **kwargs)
        if txt:
            txt = decode_html_entities(txt)
            if event:
                event.nrout += 1
                if event.displayname: txt = "[%s] %s" % (event.displayname, txt)
                if result:
                    for i in result: event.outqueue.append(i)
                event.resqueue.append(txt)
                if event.nooutput: event.ready() ; return
            else: logging.info("not putting txt on queues")
            txt = self.outputmorphs.do(txt, event)
            self.out(target, txt, how, event=event, origin=target, *args, **kwargs)

    def saynocb(self, channel, txt, result=[], how="msg", event=None, nr=375, extend=0, dot=", ", showall=False, *args, **kwargs):
        logging.warn("saying to %s (without callbacks)" % channel)
        txt = self.makeoutput(channel, txt, result, nr, extend, dot, showall=showall, *args, **kwargs)
        if txt:
            if event:
                if self.cfg.name in event.path: event.path.append(self.cfg.name)
                for i in result: event.outqueue.append(i)
                event.resqueue.append(txt)
            txt = self.outputmorphs.do(txt, event)
            self.outnocb(channel, txt, how, event=event, origin=channel, *args, **kwargs)

    def less(self, printto, what, nr=365):
        """ split up in parts of <nr> chars overflowing on word boundaries. """
        if type(what) == types.ListType: txtlist = what
        else:
            what = what.strip()
            txtlist = splittxt(what, nr)
        size = 0
        if not txtlist:   
            logging.debug("can't split txt from %s" % what)
            return ["", ""]
        res = txtlist[0]
        length = len(txtlist)
        if length > 1:
            logging.debug("addding %s lines to %s outcache (less)" % (len(txtlist), printto))
            outcache.set(u"%s-%s" % (self.cfg.name, printto), txtlist[1:])
            res += "<b> - %s more</b>" % (length - 1) 
        return [res, length]


    def reconnect(self, start=False, close=False):
        """ reconnect to the server. """
        if self.stopped: logging.warn("%s - bot is stopped .. not reconnecting" % self.cfg.name) ; return
        #self.reconnectcount = 0
        time.sleep(2)
        while 1:
            self.reconnectcount += 1
            sleepsec = self.reconnectcount * 5
            if sleepsec > 301: sleepsec = 302
            logging.warn('%s - reconnecting .. sleeping %s seconds' % (self.cfg.name, sleepsec))
            if not start: time.sleep(sleepsec)
            #start = False
            try:
                if not start: self.exit(close=close)
                if self.doreconnect(): break
            except Exception, ex: logging.error(str(ex))
            
    def doreconnect(self, start=False):
        self.started = False
        return self.start()


    def save(self, *args, **kwargs):
        """ save bot state if available. """
        if self.state: self.state.save()

    def makeresponse(self, txt, result=[], dot=", ", *args, **kwargs):
        """ create a response from a string and result list. """
        res = []
        dres = []
        if type(txt) == types.DictType or type(txt) == types.ListType:
            result = txt
        if type(result) == types.DictType:
            for key, value in result.iteritems():
                dres.append(u"%s: %s" % (key, unicode(value)))
        if dres: target = dres
        else: target = result
        if target:
            txt = u"<b>" + txt + u"</b>"
            for i in target:
                if not i: continue
                if type(i) == types.DictType:
                    for key, value in i.iteritems():
                        res.append(u"%s: %s" % (key, unicode(value)))
                else: res.append(unicode(i))
        ret = ""
        if txt: ret = unicode(txt) + dot.join(res)   
        elif res: ret =  dot.join(res)
        if ret: return ret
        return ""
    
    def send(self, *args, **kwargs):
        pass

    def sendnocb(self, *args, **kwargs):
        pass

    def normalize(self, what):
        """ convert markup to IRC bold. """
        if not what: return what
        txt = strippedtxt(what, ["\002", "\003"])
        txt = re.sub("\s+", " ", what)
        txt = stripcolor(txt)
        txt = txt.replace("\002", "*")
        txt = txt.replace("<b>", "")
        txt = txt.replace("</b>", "")
        txt = txt.replace("<i>", "")
        txt = txt.replace("</i>", "")
        txt = txt.replace("&lt;b&gt;", "*")
        txt = txt.replace("&lt;/b&gt;", "*")
        txt = txt.replace("&lt;i&gt;", "")
        txt = txt.replace("&lt;/i&gt;", "")
        return txt

    def dostart(self, botname=None, bottype=None, *args, **kwargs):
        """ create an START event and send it to callbacks. """
        e = EventBase()
        e.bot = self
        e.botname = botname or self.cfg.name
        e.bottype = bottype or self.type
        e.origin = e.botname
        e.userhost = self.cfg.name +'@' + self.cfg.uuid
        e.nolog = True
        e.channel = botname
        e.txt = "%s.%s - %s" % (e.botname, e.bottype, str(time.time()))
        e.cbtype = 'START'
        e.ttl = 1
        e.nick = self.cfg.nick or self.cfg.name
        self.doevent(e)
        logging.debug("%s - START event send to callbacks" % self.cfg.name)

    def outmonitor(self, origin, channel, txt, event=None):
        """ create an OUTPUT event with provided txt and send it to callbacks. """
        if event: e = cpy(event)
        else: e = EventBase()
        if e.status == "done":
            logging.debug("%s - outmonitor - event is done .. ignoring" % self.cfg.name)
            return
        e.bot = self
        e.origin = origin
        e.userhost = str(self.cfg.name) +'@' + str(self.cfg.uuid)
        e.auth = e.userhost
        e.channel = channel
        e.txt = txt
        e.cbtype = 'OUTPUT'
        e.nodispatch = True
        e.ttl = 1
        e.nick = self.cfg.nick or self.cfg.name
        e.bonded = True
        e.isoutput = True
        e.dontbind = True
        first_callbacks.check(self, e)

    def make_event(self, origin, channel, txt, event=None, wait=0, showall=False, nooutput=False, cbtype=""):
        """ insert an event into the callbacks chain. """
        if event: e = cpy(event)
        else: e = EventBase(bot=self)
        e.cbtype = cbtype or "CMND"
        e.origin = origin or "test@test"
        e.auth = e.origin
        e.userhost = e.origin
        e.channel = channel
        e.txt = unicode(txt)
        e.nick = e.userhost.split('@')[0]
        e.showall = showall
        e.nooutput = nooutput
        e.wait = wait
        e.closequeue = False
        e.bind(self)
        return e

    def execstr(self, origin, channel, txt, event=None, wait=0, showall=False, nooutput=False):
        e = self.make_event(origin, channel, txt, event, wait, showall, nooutput)
        return e.execwait()

    def docmnd(self, origin, channel, txt, event=None, wait=0, showall=False, nooutput=False):
        """ do a command. """
        if event: e = cpy(event)
        else: e = EventBase()   
        e.cbtype = "CMND"
        e.bot = self
        e.origin = origin
        e.auth = origin
        e.userhost = origin
        e.channel = channel
        e.txt = unicode(txt)
        e.nick = e.userhost.split('@')[0]
        e.usercmnd = e.txt.split()[0]
        e.allowqueues = True
        e.closequeue = True 
        e.showall = showall 
        e.nooutput = nooutput
        e.bind(self)
        if cmnds.woulddispatch(self, e) or e.txt[0] == "?": return self.doevent(e)

    def join(self, channel, password, *args, **kwargs):
        """ join a channel. """
        pass

    def part(self, channel, *args, **kwargs):
        """ leave a channel. """
        pass

    def action(self, channel, txt, event=None, *args, **kwargs):
        """ send action to channel. """
        pass

    def doop(self, channel, who):
        """ give nick ops. """
        pass

    def invite(self, *args, **kwargs):
        """ invite another user/bot. """
        pass

    def donick(self, nick, *args, **kwargs):
        """ do a nick change. """
        pass

    def shutdown(self, *args, **kwargs):
        """ shutdown the bot. """
        pass

    def quit(self, reason="", *args, **kwargs):
        """ close connection with the server. """
        pass

    def connect(self, reconnect=False, *args, **kwargs):
        """ connect to the server. """
        pass

    def names(self, channel, *args, **kwargs):
        """ request all names of a channel. """
        pass

    def settopic(self, channel, txt):
        pass

    def gettopic(self, channel):
        pass

    def pingcheck(self): return True
