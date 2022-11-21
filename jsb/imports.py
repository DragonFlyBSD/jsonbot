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
    mod = _import("webapp2")
    logging.debug("webapp2 module is %s" % str(mod))
    return mod


# getjson function


def getjson():
    try:
        mod = _import("json")
    except ImportError:
        mod = _import("simplejson")
    logging.debug("json module is %s" % str(mod))
    return mod


# getfeedparser function


def getfeedparser():
    mod = _import("feedparser")
    logging.info("feedparser module is %s" % str(mod))
    return mod


def getoauth():
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
    mod = _import("tornado")
    logging.info("tornado module is %s" % str(mod))
    return mod


def getBeautifulSoup():
    mod = _import("bs4")
    logging.info("BeautifulSoup module is %s" % str(mod))
    return mod


def getsleek():
    mod = _import("sleekxmpp")
    logging.info("sleek module is %s" % str(mod))
    return mod
