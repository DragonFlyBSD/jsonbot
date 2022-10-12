# jsb/commands.py
#
#

""" 
    the commands module provides the infrastructure to dispatch commands. 
    commands are the first word of a line. 

"""

## jsb imports

from threads import start_new_thread, start_bot_command
from jsb.utils.xmpp import stripped
from jsb.utils.trace import calledfrom, whichmodule
from jsb.utils.exception import handle_exception
from jsb.utils.lazydict import LazyDict
from errors import NoSuchCommand, NoSuchUser
from persiststate import UserState
from runner import cmndrunner
from boot import getcmndperms
from floodcontrol import floodcontrol
from aliases import getaliases, aliascheck

## basic imports

import logging
import sys
import types
import os
import copy
import time
import re

## defines

cpy = copy.deepcopy

## Command class

class Command(LazyDict):

    """ a command object. """

    def __init__(self, modname, cmnd, func, perms=[], threaded=False, wait=False, orig=None, how=None, speed=None):
        LazyDict.__init__(self)
        if not modname: raise Exception("modname is not set - %s" % cmnd)
        self.modname = cpy(modname)
        self.plugname = self.modname.split('.')[-1]
        self.cmnd = cpy(cmnd)
        self.orig = cpy(orig)
        self.func = func
        if type(perms) == types.StringType: perms = [perms, ]
        self.perms = cpy(perms)
        self.plugin = self.plugname
        self.threaded = cpy(threaded)
        self.wait = cpy(wait)
        self.enable = True
        self.how = how or "overwrite"
        self.regex = None
        self.speed = speed

class Commands(LazyDict):

    """
        the commands object holds all commands of the bot.
 
    """

    regex = []

    def add(self, cmnd, func, perms, threaded=False, wait=False, orig=None, how=None, speed=None, regex=False, *args, **kwargs):
        """ add a command. """
        modname = calledfrom(sys._getframe())
        try: prev = self[cmnd]
        except KeyError: prev = None
        target = Command(modname, cmnd, func, perms, threaded, wait, orig, how, speed=speed)
        if regex:
            logging.info("regex command detected - %s" % cmnd)
            self.regex.append(target)
            target.regex = cmnd 
            return self
        self[cmnd] = target
        try:
            p = cmnd.split('-')[0]
            if not self.pre: self.pre = LazyDict()
            if self.pre.has_key(p):
                if not self.pre[p]: self.pre[p] = []
                if prev in self.pre[p]: self.pre[p].remove(prev) 
                if target not in self.pre[p]: self.pre[p].append(target)
            else: self.pre[p] = [target, ]
        except IndexError: pass
        return self

    def checkre(self, bot, event):
        for r in self.regex:
            s = re.search(r.cmnd, event.stripcc().strip())
            if s:
                logging.info("regex matches %s" % r.cmnd)
                event.groups = list(s.groups())
                return r

    def wouldmatchre(self, bot, event, cmnd=""):
        groups = self.checkre(bot, event)
        if groups: return group
        
    def woulddispatch(self, bot, event):
        """ 
            dispatch an event if cmnd exists and user is allowed to exec this 
            command.

        """
        event.bind(bot)
        try:
            cmnd = event.stripcc().split()[0]
            if event.execstr and not cmnd: cmnd = event.execstr.split()[0]
            if not cmnd: cmnd = event.txt.split()[0]
        except Exception, ex: logging.debug("can't determine command") ; return None
        try:
            a = event.chan.data.aliases[cmnd]
            if a: cmnd = a.split()[0]
        except (KeyError, TypeError):
            try:
                a = getaliases()[cmnd]
                if a: cmnd = a.split()[0]
            except (KeyError, TypeError): 
                if not self.has_key(cmnd):
                    try:
                        from boot import shorttable
                        if shorttable.data.has_key(cmnd):
                            cmndlist = shorttable.data[cmnd]
                            if len(cmndlist) == 1: cmnd = cmndlist[0]
                            else: event.reply("choose one of: ", cmndlist) ; return
                    except Exception, ex: handle_exception()
        logging.info("trying for %s" % cmnd)
        result = None
        try:
            result = self[cmnd]
        except KeyError: pass
        logging.debug("woulddispatch result: %s" % result)
        if result: event.bloh() ; event.makeargs()
        return result

    def dispatch(self, bot, event, direct=False):
        """ 
            dispatch an event if cmnd exists and user is allowed to exec this 
            command.

        """
        if event.nodispatch: logging.info("nodispatch is set on event") ; return
        if event.groupchat and bot.cfg.fulljids: id = event.auth
        elif event.groupchat: id = event.auth = event.userhost
        else: id = event.auth
        if not event.user: event.bind(bot)
        if not event.user: raise NoSuchUser(event.userhost)
        self.reloadcheck(bot, event)
        c = self.woulddispatch(bot, event)
        if not c: c = self.checkre(bot, event)
        if not c: raise NoSuchCommand(event.usercmnd)
        if c.modname in bot.plugs.loading and bot.plugs.loading[c.modname]: event.reply("%s is loading" % c.modname) ; return
        if bot.cmndperms and bot.cmndperms[c.cmnd]: perms = bot.cmndperms[c.cmnd]
        else: perms = c.perms
        if bot.allowall: return self.doit(bot, event, c, direct)
        elif not bot.users or bot.users.allowed(id, perms, bot=bot): return self.doit(bot, event, c, direct)
        elif bot.users.allowed(id, perms, bot=bot): return self.doit(bot, event, c, direct)
        return event

    def doit(self, bot, event, target, direct=False):
        """ do the dispatching. """
        if not target.enable: return
        if target.modname in event.chan.data.denyplug:
             logging.warn("%s is denied in channel %s - %s" % (target.plugname, event.channel, event.userhost))
             return
        id = event.auth or event.userhost
        event.iscommand = True
        event.how = event.how or target.how or "overwrite"
        aliascheck(event)
        logging.warning('dispatching %s (%s)' % (event.usercmnd, bot.cfg.name))
        try:
            if bot.isgae:
                if not event.notask and (target.threaded or event.threaded) and not event.nothreads:
                    logging.warn("LAUNCHING AS TASK")
                    from jsb.drivers.gae.tasks import start_botevent
                    if target.threaded == "backend": start_botevent(bot, event, "backend")
                    else: start_botevent(bot, event, target.speed or event.speed)
                    event.reply("task started for %s" % event.auth)
                else: target.func(bot, event)
            else:
                if direct or event.direct: target.func(bot, event)
                elif target.threaded and not event.nothreads:
                    logging.warning("launching thread for %s (%s)" % (event.usercmnd, bot.cfg.name))
                    t = start_bot_command(target.func, (bot, event))
                    event.thread = t
                else: event.dontclose = False; cmndrunner.put(target.speed or event.speed, target.modname, target.func, bot, event)
        except Exception, ex:
            logging.error('%s - error executing %s' % (whichmodule(), str(target.func)))
            raise
        return event

    def unload(self, modname):
        """ remove modname registered commands from store. """
        delete = []
        for name, cmnd in self.iteritems():
            if not cmnd: continue
            if cmnd.modname == modname: delete.append(cmnd)
        for cmnd in delete: cmnd.enable = False
        return self

    def apropos(self, search):
        """ search existing commands for search term. """
        result = []
        from boot import getcmndtable
        for name, plugname in getcmndtable().iteritems():
            if search in name: result.append(name)
        return result

    def perms(self, cmnd):
        """ show what permissions are needed to execute cmnd. """
        try: return self[cmnd].perms
        except KeyError: return []

    def whereis(self, cmnd):
        """ return plugin name in which command is implemented. """
        from boot import getcmndtable
        try: return getcmndtable()[cmnd]
        except KeyError: return ""

    def gethelp(self, cmnd):
        """ get the docstring of a command. used for help. """
        try: return self[cmnd].func.__doc__
        except KeyError: pass

    def reloadcheck(self, bot, event, target=None):
        """
            check if event requires a plugin to be reloaded. if so 
            reload the plugin.  

        """
        from boot import getcmndtable
        from boot import plugblacklist
        plugloaded = None
        plugin = None
        target = target or event.usercmnd.lower()
        from jsb.lib.aliases import getaliases
        aliases = getaliases()
        try: target = aliases[target]
        except KeyError:
            try: target = event.chan.data.aliases[target]
            except (AttributeError, KeyError, TypeError): pass
            if not getcmndtable().has_key(target):
                try:
                    from boot import shorttable
                    if shorttable.data.has_key(target):
                        cmndlist = shorttable.data[target]
                        if len(cmndlist) == 1: target = cmndlist[0]
                except Exception, ex: handle_exception()
        if target: target = target.split()[0]
        logging.debug("checking for reload of %s" % target)
        try:
            plugin = getcmndtable()[target]
        except KeyError:
            try:
                from boot import retable
                for regex, mod in retable.data.iteritems():
                    if re.search(regex, event.stripcc() or event.txt): plugin = mod ; break
            except Exception, ex: handle_exception()
        logging.info("plugin is %s" % plugin)
        if not plugin: logging.debug("can't find plugin to reload for %s" % target) ; return
        if plugin in bot.plugs: logging.info(" %s already loaded" % plugin) ; return plugloaded
        elif plugin in plugblacklist.data: return plugloaded
        elif bot.cfg.loadlist and plugin not in bot.cfg.loadlist: logging.warn("plugin %s is blacklisted" % plugin) ; return plugloaded
        logging.info("loaded %s on demand" % plugin)
        plugloaded = bot.plugs.reload(plugin)
        return plugloaded

## global commands

cmnds = Commands()

def size():
    return len(cmnds)
