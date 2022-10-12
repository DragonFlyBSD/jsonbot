# jsb/persist.py
#
#

"""
    allow data to be written to disk or BigTable in JSON format. creating 
    the persisted object restores data. 

"""

## jsb imports

from jsb.utils.trace import whichmodule, calledfrom, callstack, where
from jsb.utils.lazydict import LazyDict
from jsb.utils.exception import handle_exception
from jsb.utils.name import stripname
from jsb.utils.locking import lockdec
from jsb.utils.timeutils import elapsedstring
from jsb.lib.callbacks import callbacks
from jsb.lib.errors import MemcachedCounterError, JSONParseError

from datadir import getdatadir

## simplejson imports

from jsb.imports import getjson
json = getjson()

## basic imports

from collections import deque
import thread
import logging
import os
import os.path
import types
import copy
import sys
import time

## defines

cpy = copy.deepcopy

## locks


persistlock = thread.allocate_lock()
persistlocked = lockdec(persistlock)

## global list to keeptrack of what persist objects need to be saved

needsaving = deque()

def cleanup(bot=None, event=None):
    global needsaving
    todo = cpy(needsaving)
    r = []
    for p in todo:
        try: p.dosave() ; r.append(p) ; logging.warn("saved on retry - %s" % p.fn)
        except (OSError, IOError), ex: logging.error("failed to save %s - %s" % (p, str(ex)))
    for p in r:
        try: needsaving.remove(p)
        except ValueError: pass
    return needsaving


## try google first

try:
    from google.appengine.ext.db.metadata import Kind
    from google.appengine.ext import db
    import google.appengine.api.memcache as mc
    from google.appengine.api.datastore_errors import Timeout, TransactionFailedError
    from cache import get, set, delete
    logging.debug("using BigTable based Persist")

    ## JSONindb class

    class JSONindb(db.Model):
        """ model to store json files in. """
        modtime = db.DateTimeProperty(auto_now=True, indexed=False)
        createtime = db.DateTimeProperty(auto_now_add=True, indexed=False)
        filename = db.StringProperty()
        content = db.TextProperty(indexed=False)

    ## Persist class

    class Persist(object):

        """ persist data attribute to database backed JSON file. """ 

        def __init__(self, filename, default={}, type="cache"):
            self.cachtype = None
            self.plugname = calledfrom(sys._getframe())
            if 'lib' in self.plugname: self.plugname = calledfrom(sys._getframe(1))
            try: del self.fn
            except: pass 
            self.fn = unicode(filename.strip()) # filename to save to
            self.logname = os.sep.join(self.fn.split(os.sep)[-1:])
            self.countername = self.fn + "_" + "counter"
            self.mcounter = mc.get(self.countername) or mc.set(self.countername, "1")
            try: self.mcounter = int(self.mcounter)
            except ValueError: logging.warn("can't parse %s mcounter, setting to zero: %s" % (self.fn, self.mcounter)) ; self.mcounter = 0
            self.data = None
            self.type = type
            self.counter = self.mcounter
            self.key = None
            self.obj = None
            self.size = 0
            self.jsontxt = ""
            self.init(default)

        def init(self, default={}, filename=None):
            if self.checkmc(): self.jsontxt = self.updatemc() ; self.cachetype = "cache"
            else:
                tmp = get(self.fn)
                self.cachetype = "mem"
                if tmp != None:
                    logging.warn("*%s* - loaded %s" % (self.cachetype, self.fn))
                    self.data = tmp
                    if type(self.data) == types.DictType: self.data = LazyDict(self.data)
                    return self.data
            if self.jsontxt == "": self.cachetype = "cache" ; self.jsontxt = mc.get(self.fn)
            if self.jsontxt == None: 
                self.cachetype = "db"
                logging.debug("%s - loading from db" % self.fn) 
                try:
                    try: self.obj = JSONindb.get_by_key_name(self.fn)
                    except Timeout: self.obj = JSONindb.get_by_key_name(self.fn)
                except Exception, ex:
                    # bw compat sucks
                    try: self.obj = JSONindb.get_by_key_name(self.fn)
                    except Exception, ex:
                        handle_exception()
                        self.obj = None
                if self.obj == None:
                    logging.warn("%s - no entry found, using default" % self.fn)
                    self.jsontext = json.dumps(default) ; self.cachetype = "default"
                else:
                    self.jsontxt = self.obj.content; self.cachetype = "db"
                if self.jsontxt:
                    mc.set(self.fn, self.jsontxt)
                    incr = mc.incr(self.countername)
                    if incr:
                        try: self.mcounter = self.counter = int(incr)
                        except ValueError: logging.error("can't make counter out of %s" % incr) 
                    else: self.mcounter = 1
            logging.debug("memcached counters for %s: %s" % (self.fn, self.mcounter))
            if self.jsontxt == None: self.jsontxt = json.dumps(default) 
            logging.warn('%s - jsontxt is %s' % (self.fn, self.jsontxt))
            try:
                self.data = json.loads(self.jsontxt)
            except: raise JSONParseError(self.fn)
            if not self.data: self.data = default
            self.size = len(self.jsontxt)
            if type(self.data) == types.DictType: self.data = LazyDict(self.data)
            set(self.fn, self.data)
            logging.warn("*%s* - loaded %s (%s)" % (self.cachetype, self.fn, len(self.jsontxt)))

        def get(self):
            logging.debug("getting %s from local cache" % self.fn)
            a = get(self.fn)
            logging.debug("got %s from local cache" % type(a))
            return a

        def sync(self):
            logging.debug("syncing %s" % self.fn)
            tmp = cpy(self.data)
            data = json.dumps(tmp)
            mc.set(self.fn, data)
            if type(self.data) == types.DictType:
                self.data = LazyDict(self.data)
            set(self.fn, self.data)
            return data

        def updatemc(self):
            tmp = mc.get(self.fn)
            if tmp != None:
                try:
                    t = json.loads(tmp)
                    if self.data: t.update(self.data)
                    self.data = LazyDict(t)
                    logging.warn("updated %s" % self.fn)
                except AttributeError, ex: logging.warn(str(ex))
                return self.data

        def checkmc(self):
            try:
                self.mcounter = int(mc.get(self.countername)) or 0
            except: self.mcounter = 0
            logging.warn("mcounter for %s is %s (%s)" % (self.fn, self.mcounter, self.counter))
            if (self.mcounter - self.counter) < 0: return True
            elif (self.mcounter - self.counter) > 0: return True
            return False

        def save(self):
            cleanup()
            global needsaving
            try: self.dosave()
            except (IOError, OSError, TransactionFailedError):
                handle_exception()
                logging.error("PUSHED ON RETRY QUEUE") 
                self.sync()
                if self not in needsaving: needsaving.appendleft(self)

        @persistlocked
        def dosave(self, filename=None):
            """ save json data to database. """
            if self.checkmc(): self.updatemc()
            fn = filename or self.fn
            bla = json.dumps(self.data)
            if filename or self.obj == None:
                self.obj = JSONindb(key_name=fn)
                self.obj.content = bla
            else: self.obj.content = bla
            self.obj.filename = fn
            from google.appengine.ext import db
            key = db.run_in_transaction(self.obj.put)
            logging.debug("transaction returned %s" % key)
            mc.set(fn, bla)
            if type(self.data) == types.DictType: self.data = LazyDict(self.data)
            set(fn, self.data)
            incr = mc.incr(self.countername)
            if incr:
                try: self.mcounter = self.counter = int(incr)
                except ValueError: logging.error("can't make counter out of %s" % incr) 
            else: self.mcounter = 1
            self.counter = self.mcounter
            logging.debug("memcached counters for %s: %s" % (fn, self.mcounter))
            logging.warn('saved %s (%s)' % (fn, len(bla)))
            logging.debug('saved %s from %s' % (fn, where()))

        def upgrade(self, filename):
            self.init(self.data, filename=filename)

    ## findfilenames function 

    def findfilenames(target, filter=[], skip=[]):
        res = []
        targetkey = db.Key.from_path(JSONindb.kind(), target)
        targetkey2 = db.Key.from_path(JSONindb.kind(), target + "zzz")
        logging.warn("key for %s is %s" % (target, str(targetkey)))
        q = db.Query(JSONindb, keys_only=True)
        q.filter("__key__ >", targetkey)
        q.filter("__key__ <", targetkey2)
        for key in q:
            fname = key.name()
            if fname in skip: continue
            fname = str(fname)
            logging.warn("using %s" % fname)
            go = True
            for fil in filter:
                if fil not in fname.lower(): go = False ; break
            if not go: continue
            res.append(fname)
        return res

    def findnames(target, filter=[], skip=[]):
        res = []
        for f in findfilenames(target, filter, skip):
            res.append(f.split(os.sep)[-1])
        return res


except ImportError:

    ## file based persist

    logging.debug("using file based Persist")


    ## imports for shell bots

    if True:
        got = False
        from jsb.memcached import getmc
        mc = getmc()
        if mc:
            status = mc.get_stats()
            if status:
                logging.warn("memcached uptime is %s" % elapsedstring(status[0][1]['uptime']))
                got = True
        if got == False:
            logging.debug("no memcached found - using own cache")
        from cache import get, set, delete

    import fcntl

    ## classes

    class Persist(object):

        """ persist data attribute to JSON file. """
        
        def __init__(self, filename, default=None, init=True, postfix=None):
            """ Persist constructor """
            if postfix: self.fn = str(filename.strip()) + str("-%s" % postfix)
            else: self.fn = str(filename.strip())
            self.lock = thread.allocate_lock() # lock used when saving)
            self.data = LazyDict(default=default) # attribute to hold the data
            try:
                res = []
                target = getdatadir().split(os.sep)[-1]
                for i in self.fn.split(os.sep)[::-1]:
                    if target in i: break
                    res.append(i)
                self.logname = os.sep.join(res[::-1])
                if not self.logname: self.logname = self.fn
            except: handle_exception() ; self.logname = self.fn
            self.countername = self.fn + "_" + "counter"
            if got:
                count = mc.get(self.countername)
                try:
                    self.mcounter = self.counter = int(count)
                except (ValueError, TypeError):
                    self.mcounter = self.counter = mc.set(self.countername, "1") or 0
            else:
                self.mcounter = self.counter = 0
            self.ssize = 0
            self.jsontxt = ""
            self.dontsave = False
            if init:
                self.init(default)
                if default == None: default = LazyDict()

        def size(self):
            return "%s (%s)" % (len(self.data), len(self.jsontxt))

        def init(self, default={}, filename=None):
            """ initialize the data. """
            gotcache = False
            cachetype = "cache"
            try:
                logging.debug("using name %s" % self.fn)
                a = get(self.fn)
                if a: self.data = a
                else: self.data = None
                if self.data != None:
                    logging.debug("got data from local cache")
                    return self
                if got: self.jsontxt = mc.get(self.fn) ; cachetype = "cache"
                if not self.jsontxt:
                   datafile = open(self.fn, 'r')
                   self.jsontxt = datafile.read()
                   datafile.close()
                   self.ssize = len(self.jsontxt)
                   cachetype = "file"
                   if got: mc.set(self.fn, self.jsontxt)
            except IOError, ex:
                if not 'No such file' in str(ex):
                    logging.error('failed to read %s: %s' % (self.fn, str(ex)))
                    raise
                else:
                    logging.debug("%s doesn't exist yet" % self.fn)
                    self.jsontxt = json.dumps(default)
            try:
                if self.jsontxt:
                    logging.debug(u"loading: %s" % type(self.jsontxt))
                    try: self.data = json.loads(str(self.jsontxt))
                    except Exception, ex: logging.error("couldn't parse %s" % self.jsontxt) ; self.data = None ; self.dontsave = True
                if not self.data: self.data = LazyDict()
                elif type(self.data) == types.DictType:
                    logging.debug("converting dict to LazyDict")
                    d = LazyDict()
                    d.update(self.data)
                    self.data = d
                set(self.fn, self.data)
                logging.debug("loaded %s - %s" % (self.logname, cachetype))
            except Exception, ex:
                logging.error('ERROR: %s' % self.fn)
                raise

        def upgrade(self, filename):
            self.init(self.data, filename=filename)
            self.save(filename)

        def get(self):
            logging.debug("getting %s from local cache" % self.fn)
            a = get(self.fn)
            logging.debug("got %s from local cache" % type(a))
            return a

        def sync(self):
            logging.debug("syncing %s" % self.fn)
            if got: mc.set(self.fn, json.dumps(self.data))
            set(self.fn, self.data)
            return self

        def save(self):
            cleanup()
            global needsaving
            try: self.dosave()
            except (IOError, OSError):
                self.sync()
                if self not in needsaving: needsaving.append(self)

        @persistlocked
        def dosave(self):
            """ persist data attribute. """
            try:
                if self.dontsave: logging.error("dontsave is set on  %s - not saving" % self.fn) ; return
                fn = self.fn
                if got: self.mcounter = int(mc.incr(self.countername))
                if got and (self.mcounter - self.counter) > 1:
                    tmp = json.loads(mc.get(fn))
                    if tmp:
                        try: tmp.update(self.data) ; self.data = LazyDict(tmp) ; logging.warn("updated %s" % fn)
                        except AttributeError: pass
                    self.counter = self.mcounter
                d = []
                if fn.startswith(os.sep): d = [os.sep,]
                for p in fn.split(os.sep)[:-1]:
                    if not p: continue
                    d.append(p)
                    pp = os.sep.join(d)
                    if not os.path.isdir(pp):
                        logging.warn("creating %s dir" % pp)
                        os.mkdir(pp)
                tmp = fn + '.tmp' # tmp file to save to
                datafile = open(tmp, 'w')
                fcntl.flock(datafile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                json.dump(self.data, datafile, indent=True)
                fcntl.flock(datafile, fcntl.LOCK_UN)
                datafile.close()
                try: os.rename(tmp, fn)
                except (IOError, OSError):
                    os.remove(fn)
                    os.rename(tmp, fn)
                jsontxt = json.dumps(self.data)
                logging.debug("setting cache %s - %s" % (fn, jsontxt))
                self.jsontxt = jsontxt
                set(fn, self.data)
                if got: mc.set(fn, jsontxt)
                logging.info('%s saved' % self.logname)
            except IOError, ex: logging.error("not saving %s: %s" % (self.fn, str(ex))) ; raise
            except: raise
            finally: pass

    ## findfilenames function 

    def findfilenames(target, filter=[], skip=[]):
        res = []
        if not os.path.isdir(target): return res
        for f in os.listdir(target):
            if f in skip: continue
            fname = target + os.sep + f
            if os.path.isdir(fname): res.extend(findfilenames(fname, skip))
            go = True
            for fil in filter:
                if fil not in fname.lower(): go = False ; break
            if not go: continue
            res.append(fname)
        return res

    def findnames(target, filter=[], skip=[]):
        res = []
        for f in findfilenames(target, filter, skip):
            res.append(f.split(os.sep)[-1])
        return res


class PlugPersist(Persist):

    """ persist plug related data. data is stored in jsondata/plugs/{plugname}/{filename}. """

    def __init__(self, filename, default={}, *args, **kwargs):
        plugname = calledfrom(sys._getframe())
        Persist.__init__(self, getdatadir() + os.sep + 'plugs' + os.sep + stripname(plugname) + os.sep + stripname(filename), default=default, *args, **kwargs)

class GlobalPersist(Persist):

    """ persist plug related data. data is stored in jsondata/plugs/{plugname}/{filename}. """

    def __init__(self, filename, default={}, *args, **kwargs):
        if not filename: raise Exception("filename not set in GlobalPersist")
        logging.warn("filename is %s" % filename)
        Persist.__init__(self, getdatadir() + os.sep + 'globals' + os.sep + stripname(filename), default=default, *args, **kwargs)

## PersistCollection class

class PersistCollection(object):

    """ maintain a collection of Persist objects. """

    def __init__(self, path, *args, **kwargs):
        assert path
        self.path = path
        d = [os.sep, ]
        for p in path.split(os.sep):
            if not p: continue
            d.append(p)
            pp = os.sep.join(d)
            try:
                os.mkdir(pp)
                logging.warn("creating %s dir" % pp)
            except OSError, ex:
                if 'Errno 13' in str(ex) or 'Errno 2' in str(ex): continue
                logging.warn("can't make %s - %s" % (pp,str(ex))) ; continue
                
    def filenames(self, filter=[], path=None, skip=[], result=[]):
        target = path or self.path
        res = findfilenames(target, filter, skip)
        logging.info("filenames are %s" % str(res))
        return res

    def names(self, filter=[], path=None, skip=[], result=[]):
        target = path or self.path
        res = findnames(target, filter, skip)
        return res

    def search(self, field, target):
        res = []
        for obj in self.objects().values():
            try: item = getattr(obj.data, field)
            except AttributeError: handle_exception() ; continue
            if not item: continue
            if target in item: res.append(obj)
        return res
            
    def objects(self, filter=[], path=None):
        if type(filter) != types.ListType: filter = [filter, ] 
        res = {}
        target = path or self.path
        for f in self.filenames(filter, target):
             res[f] = Persist(f)
        return res

## PlugPersistCollection class

class PlugPersistCollection(PersistCollection):

    def __init__(self):
        plugname = calledfrom(sys._getframe())
        self.path =  getdatadir() + os.sep + 'plugs' + os.sep + stripname(plugname) + os.sep
        PersistCollection.__init__(self, self.path)

## GlobalPersistCollection class

class GlobalPersistCollection(PersistCollection):

    def __init__(self):
        self.path =  getdatadir() + os.sep + 'globals'
        GlobalCollection(self, self.path)


callbacks.add("TICK60", cleanup)
