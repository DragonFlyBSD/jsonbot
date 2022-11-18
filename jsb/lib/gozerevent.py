# jsb/gozerevent.py
#
#

"""
    basic event used in jsb. supports json dumping and loading plus toxml
    functionality.
"""

# jsb imports

import logging

from jsb.drivers.xmpp.namespace import attributes, subelements
from jsb.lib.eventbase import EventBase
from jsb.utils.url import striphtml

# dom imports


# for exceptions


# xmpp imports


# basic imports


# GozerEvent class


class GozerEvent(EventBase):

    """dictionairy to store xml stanza attributes."""

    def __init__(self, input={}):
        if input is None:
            EventBase.__init__(self)
        else:
            EventBase.__init__(self, input)
        try:
            self["fromm"] = self["from"]
        except (KeyError, TypeError):
            self["fromm"] = ""

    def __getattr__(self, name):
        """override getattribute so nodes in payload can be accessed."""
        if name not in self and "subelements" in self:
            for i in self["subelements"]:
                if name in i:
                    return i[name]
        return EventBase.__getattr__(self, name, default="")

    def get(self, name):
        """get a attribute by name."""
        if "subelements" in self:
            for i in self["subelements"]:
                if name in i:
                    return i[name]
        if name in self:
            return self[name]
        return EventBase()

    def tojabber(self):
        """convert the dictionary to xml."""
        raise ImportError(
            "This module requires XML library. It used to use xmlstream which is no longer maintained. Please find an alternative library and refactor this function"
        )
        from xmlstream import NodeBuilder, XMLescape, XMLunescape

        res = dict(self)
        if not res:
            raise Exception("%s .. toxml() can't convert empty dict" % self.name)
        elem = self["element"]
        main = "<%s" % self["element"]
        for attribute in attributes[elem]:
            if attribute in res:
                if res[attribute]:
                    main += " %s='%s'" % (attribute, XMLescape(res[attribute]))
                continue
        main += ">"
        if "xmlns" in res:
            main += "<x xmlns='%s'/>" % res["xmlns"]
            gotsub = True
        else:
            gotsub = False
        if "html" in res:
            if res["html"]:
                main += (
                    '<html xmlns="http://jabber.org/protocol/xhtml-im"><body xmlns="http://www.w3.org/1999/xhtml">%s</body></html>'
                    % res["html"]
                )
                gotsub = True
        if "txt" in res:
            if res["txt"]:
                main += "<body>%s</body>" % XMLescape(res["txt"])
                gotsub = True
        for subelement in subelements[elem]:
            if subelement == "body":
                continue
            if subelement == "thread":
                continue
            try:
                data = res[subelement]
                if data:
                    try:
                        main += "<%s>%s</%s>" % (
                            subelement,
                            XMLescape(data),
                            subelement,
                        )
                        gotsub = True
                    except AttributeError as ex:
                        logging.warn("skipping %s" % subelement)
            except KeyError:
                pass
        if gotsub:
            main += "</%s>" % elem
        else:
            main = main[:-1]
            main += " />"
        return main

    toxml = tojabber

    def str(self):
        """convert to string."""
        result = ""
        elem = self["element"]
        for item, value in dict(self).items():
            if item in attributes[elem] or item in subelements[elem] or item == "txt":
                result += "%s='%s' " % (item, value)
        return result
