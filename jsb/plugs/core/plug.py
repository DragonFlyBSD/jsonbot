# jsb/plugs/core/plug.py
#
#

""" plugin management. """

# jsb imports

import logging

from jsb.lib.boot import (default_plugins, plugdisable, plugenable,
                          plugin_packages, remove_plugin, savecmndtable,
                          savepluginlist, update_mod)
from jsb.lib.commands import cmnds
from jsb.lib.errors import NoSuchPlugin, RequireError
from jsb.lib.examples import examples
from jsb.utils.exception import exceptionmsg, handle_exception

# basic imports


# plug-enable command


def handle_plugenable(bot, event):
    """arguments" <plugname> - enable a plugin."""
    if not event.rest:
        event.missing("<plugname>")
        return
    if "." in event.rest:
        mod = event.rest
    else:
        mod = bot.plugs.getmodule(event.rest)
    if not mod:
        event.reply("can't find module for %s" % event.rest)
        return
    event.reply("reloading and enabling %s" % mod)
    plugenable(mod)
    bot.do_enable(mod)
    bot.plugs.reload(mod, force=True)
    update_mod(mod)
    event.done()


cmnds.add(
    "plug-enable",
    handle_plugenable,
    [
        "OPER",
    ],
)
examples.add("plug-enable", "enable a plugin", "plug-enable rss")

# plug-disable command


def handle_plugdisable(bot, event):
    """arguments: <plugname> - disable a plugin."""
    if not event.rest:
        event.missing("<plugin>")
        return
    mod = bot.plugs.getmodule(event.rest)
    if mod in default_plugins:
        event.reply("can't remove a default plugin")
        return
    if not mod:
        event.reply("can't find module for %s" % event.rest)
        return
    event.reply("unloading and disabling %s" % mod)
    bot.plugs.unload(mod)
    plugdisable(mod)
    bot.do_disable(mod)
    event.done()


cmnds.add(
    "plug-disable",
    handle_plugdisable,
    [
        "OPER",
    ],
)
examples.add("plug-disable", "disable a plugin", "plug-disable rss")

# plug-reload command


def handle_plugreload(bot, ievent):
    """arguments: <list of plugnames> - reload list of plugins."""
    try:
        pluglist = ievent.args
    except IndexError:
        ievent.missing("<list of plugnames>")
        return
    reloaded = []
    errors = []
    for plug in pluglist:
        modname = bot.plugs.getmodule(plug)
        if not modname:
            errors.append("can't find %s plugin" % plug)
            continue
        try:
            loaded = bot.plugs.reload(modname, force=True, showerror=True)
            for plug in loaded:
                reloaded.append(plug)
                logging.warn("%s reloaded" % plug)
        except RequireError as ex:
            errors.append(str(ex))
            continue
        except NoSuchPlugin:
            errors.append("can't find %s plugin" % plug)
            continue
        except Exception as ex:
            if "No module named" in str(ex) and plug in str(ex):
                logging.debug("%s - %s" % (modname, str(ex)))
                continue
            errors.append(exceptionmsg())
    for modname in reloaded:
        if modname:
            update_mod(modname)
    if errors:
        ievent.reply("errors: ", errors)
    if reloaded:
        ievent.reply("reloaded: ", reloaded)


cmnds.add("plug-reload", handle_plugreload, "OPER")
examples.add("plug-reload", "plug-reload <plugin>", "plug-reload core")
