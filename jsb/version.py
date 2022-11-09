# jsb/version.py
#
#

""" version related stuff. """

## jsb imports

from jsb.lib.config import getmainconfig

## basic imports

import binascii

## defines

version = "0.84.4"
__version__ = version

## getversion function


def getversion(txt=""):
    """return a version string."""
    return "JSONBOT %s RELEASE %s" % (version, txt)
