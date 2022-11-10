# jsb/imports.py
#
#

""" provide a import wrappers for the contrib packages. """

# lib imports

import logging

from .lib.jsbimport import _import

# basic imports


# getdns function


def getdns():
    try:
        mod = _import("dns")
    except:
        mod = None
    logging.debug("imports - dns module is %s" % str(mod))
    return mod


def getwebapp2():
    try:
        mod = _import("webapp2")
    except:
        mod = _import("webapp2")
    logging.debug("webapp2 module is %s" % str(mod))
    return mod


# getjson function


def getjson():
    try:
        pass

        # mod = _import("simplejson")
        mod = _import("json")
    except ImportError:
        try:
            mod = _import("json")
        except:
            try:
                mod = _import("simplejson")
            except:
                mod = _import("simplejson")
    logging.debug("json module is %s" % str(mod))
    return mod


# getfeedparser function


def getfeedparser():
    try:
        mod = _import("feedparser")
    except:
        mod = _import("feedparser")
    logging.info("feedparser module is %s" % str(mod))
    return mod


def getoauth():
    try:
        mod = _import("oauth")
    except:
        mod = _import("oauth")
    logging.info("oauth module is %s" % str(mod))
    return mod


def getrequests():
    try:
        mod = _import("requests")
    except:
        mod = None
    logging.info("requests module is %s" % str(mod))
    return mod


def gettornado():
    try:
        mod = _import("tornado")
    except:
        mod = _import("tornado")
    logging.info("tornado module is %s" % str(mod))
    return mod


def getBeautifulSoup():
    try:
        mod = _import("BeautifulSoup")
    except:
        mod = _import("BeautifulSoup")
    logging.info("BeautifulSoup module is %s" % str(mod))
    return mod


def getsleek():
    try:
        mod = _import("sleekxmpp")
    except:
        mod = _import("sleekxmpp")
    logging.info("sleek module is %s" % str(mod))
    return mod
