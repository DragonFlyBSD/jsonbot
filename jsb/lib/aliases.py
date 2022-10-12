# jsb/lib/aliases.py
#
#

""" global aliases. """

## jsb imports

from jsb.lib.datadir import getdatadir
from jsb.utils.lazydict import LazyDict

## basic imports

import os
import logging

## defines

aliases = LazyDict()

## getaliases function

def getaliases(ddir=None, force=True):
    """ return global aliases. """
    global aliases
    if not aliases or force:
        from jsb.lib.persist import Persist
        from jsb.utils.lazydict import LazyDict
        d = ddir or getdatadir()
        p = Persist(d + os.sep + "run" + os.sep + "aliases")
        if not p.data: p.data = LazyDict()
        aliases = p.data
    return aliases

def savealiases(ddir=None):
    """ return global aliases. """
    global aliases
    if aliases:
        logging.warn("saving aliases")
        from jsb.lib.persist import Persist
        from jsb.utils.lazydict import LazyDict
        d = ddir or getdatadir()
        p = Persist(d + os.sep + "run" + os.sep + "aliases")
        p.data = aliases
        p.save()
    return aliases

def aliascheck(ievent):
    """ check if alias is available. """
    if not ievent.execstr: return
    try:
        cmnd = ievent.execstr.split()[0]
        alias = aliases[cmnd]
        ievent.txt = ievent.txt.replace(cmnd, alias, 1)
        ievent.execstr = ievent.execstr.replace(cmnd, alias, 1)
        ievent.alias = alias
        ievent.aliased = cmnd
        ievent.prepare()
    except (IndexError, KeyError): pass


def size():
    return len(aliases)

def setalias(first, second):
    global aliases
    aliases[first] = second
