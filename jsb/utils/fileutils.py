# jsb/utils/fileutils.py
#
# Description: Various file utilities
# Author: Wijnand 'tehmaze' Modderman
# Author URL: http://tehmaze.com
# License: BSD

""" provide file related helpers. """

# jsb imports

import bz2
import gzip
import io
import os
import tarfile

from jsb.utils.generic import istr

# basic imports


# tarextract function


def tarextract(package, fileobj=None, prefix=None, base=None):
    """
    Extracts a tarball from ``package``, or, if ``fileobj`` is either a string or a seekable
    IO stream, it will extract the data from there. We only extract files from the tarball
    that are member of the ``base`` directory if a ``base`` is specified.

    """
    extracted = []
    if fileobj:
        if type(fileobj) == bytes:
            fileobj = io.StringIO(fileobj)
        tarf = tarfile.open(mode="r|", fileobj=fileobj)
    else:
        tarf = tarfile.open(package, "r")
    for tarinfo in tarf:
        if tarinfo.name.startswith("/"):
            tarinfo.name = tarinfo.name[1:]  # strip leading /
        if not base or (
            (tarinfo.name.rstrip("/") == base and tarinfo.isdir())
            or tarinfo.name.startswith(base + os.sep)
        ):
            if prefix:
                tarinfo.name = "/".join([prefix, tarinfo.name])
            tarf.extract(tarinfo)
            extracted.append(tarinfo.name)
    tarf.close()
    if fileobj:
        try:
            fileobj.close()
        except:
            pass
        del fileobj
    return extracted


# unzip functions


def bunzip2(fileobj):
    """bunzip2 the file object."""
    return bz2.decompress(fileobj)


def gunzip(fileobj):
    """gunzip the file object."""
    if type(fileobj) == bytes or isinstance(fileobj, istr):
        fileobj = io.StringIO(str(fileobj))
    return gzip.GzipFile(mode="rb", fileobj=fileobj).read()


# mtime functions


def mtime(path):
    """return last modification time."""
    try:
        return os.stat(os.getcwd + os.sep + package.replace(".", os.sep))[stat.ST_MTIME]
    except:
        pass
