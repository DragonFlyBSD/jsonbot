#!/usr/bin/env python
#
#

target = "jsb"  # BHJTW change this to /var/cache/jsb on debian

import os

try:
    from setuptools import setup
except:
    print("i need setuptools to properly install JSONBOT")
    os._exit(1)

upload = []


def uploadfiles(dir):
    upl = []
    if not os.path.isdir(dir):
        print("%s does not exist" % dir)
        os._exit(1)
    for file in os.listdir(dir):
        if not file or file.startswith("."):
            continue
        d = dir + os.sep + file
        if not os.path.isdir(d):
            if file.endswith(".pyc"):
                continue
            upl.append(d)
    return upl


def uploadlist(dir):
    upl = []

    for file in os.listdir(dir):
        if not file or file.startswith("."):
            continue
        d = dir + os.sep + file
        if os.path.isdir(d):
            upl.extend(uploadlist(d))
        else:
            if file.endswith(".pyc"):
                continue
            upl.append(d)

    return upl


setup(
    name="jsb",
    version="0.84.4",
    url="http://jsonbot.googlecode.com/",
    download_url="http://code.google.com/p/jsonbot/downloads",
    author="Bart Thate",
    author_email="bthate@gmail.com",
    description="The bot for you!",
    license="MIT",
    include_package_data=True,
    zip_safe=False,
    scripts=[
        "bin/jsb",
        "bin/jsb-backup",
        "bin/jsb-init",
        "bin/jsb-irc",
        "bin/jsb-fleet",
        "bin/jsb-xmpp",
        "bin/jsb-sed",
        "bin/jsb-sleek",
        "bin/jsb-stop",
        "bin/jsb-tornado",
        "bin/jsb-udp",
    ],
    packages=[
        "jsb",
        "jsb.api",
        "jsb.lib",
        "jsb.lib.rest",
        "jsb.db",
        "jsb.drivers",
        "jsb.drivers.console",
        "jsb.drivers.convore",
        "jsb.drivers.irc",
        "jsb.drivers.sleek",
        "jsb.drivers.tornado",
        "jsb.drivers.xmpp",
        "jsb.utils",
        "jsb.plugs",
        "jsb.plugs.db",
        "jsb.plugs.core",
        "jsb.plugs.common",
        "jsb.plugs.socket",
        "jsb.plugs.myplugs",
        "jsb.plugs.myplugs.socket",
        "jsb.plugs.myplugs.common",
    ],
    long_description=""" JSONBOT is a remote event-driven framework for building bots that talk JSON to each other over XMPP. This distribution has IRC/Console/XMPP/WWW/Convore bots built on this framework. """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    data_files=[
        (target + os.sep + "data", uploadfiles("jsb" + os.sep + "data")),
        (
            target + os.sep + "data" + os.sep + "examples",
            uploadlist("jsb" + os.sep + "data" + os.sep + "examples"),
        ),
        (
            target + os.sep + "data" + os.sep + "static",
            uploadlist("jsb" + os.sep + "data" + os.sep + "static"),
        ),
        (
            target + os.sep + "data" + os.sep + "templates",
            uploadlist("jsb" + os.sep + "data" + os.sep + "templates"),
        ),
    ],
    package_data={
        "": ["*.crt"],
    },
)
