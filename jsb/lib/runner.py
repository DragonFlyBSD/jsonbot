# jsb/runner.py
#
#

""" threads management to run jobs. """

## jsb imports

from jsb.lib.threads import getname, start_new_thread, start_bot_command
from jsb.utils.exception import handle_exception
from jsb.utils.locking import locked, lockdec
from jsb.utils.lockmanager import rlockmanager, lockmanager
from jsb.utils.generic import waitevents
from jsb.utils.trace import callstack, whichmodule
from jsb.lib.threadloop import RunnerLoop
from jsb.lib.callbacks import callbacks
from jsb.lib.errors import URLNotEnabled

## basic imports

import Queue
import time
import thread
import random
import logging
import sys

## Runner class

class Runner(RunnerLoop):

    """
        a runner is a thread with a queue on which jobs can be pushed. 
        jobs scheduled should not take too long since only one job can 
        be executed in a Runner at the same time.

    """

    def __init__(self, name="runner", doready=True):
        RunnerLoop.__init__(self, name)
        self.working = False
        self.starttime = time.time()
        self.elapsed = self.starttime
        self.finished = time.time()
        self.doready = doready
        self.nowrunning = ""
        self.longrunning = []
        self.shortrunning = []
        
    def handle(self, descr, func, *args, **kwargs):
        """ schedule a job. """
        self.working = True
        try:
            #rlockmanager.acquire(getname(str(func)))
            logging.debug('running %s: %s' % (descr, self.nowrunning))
            self.starttime = time.time()
            func(*args, **kwargs)
            self.finished = time.time()
            self.elapsed = self.finished - self.starttime
            if self.elapsed > 5:
                logging.debug('ALERT %s %s job taking too long: %s seconds' % (descr, str(func), self.elapsed))
        except Exception, ex: handle_exception()
        #finally: rlockmanager.release()
        self.working = False

    def done(self, event):
        try: int(event.cbtype)
        except ValueError:
            if event.cbtype not in ['TICK', 'PING', 'NOTICE', 'TICK60']: logging.warn(str(event.cbtype))
                            
## BotEventRunner class

class BotEventRunner(Runner):

    def handle(self, speed, args):
        """ schedule a bot command. """
        try:
            descr, func, bot, ievent = args
            self.starttime = time.time()
            #lockmanager.acquire(getname(str(func)))
            if not ievent.nolog: logging.debug("event handler is %s" % str(func))
            if self.nowrunning in self.longrunning: 
                logging.warn("putting %s on longrunner" % self.nowrunning)
                longrunner.put(ievent.speed or speed, descr, func, bot, ievent)
                return
            self.working = True
            try: func(bot, ievent)
            except URLNotEnabled: logging.warn("urls fetching is disabled (%s)" % ievent.usercmnd) ; return
            self.finished = time.time()
            self.elapsed = self.finished - self.starttime
            if self.elapsed > 5:
                if self.nowrunning not in self.longrunning: self.longrunning.append(self.nowrunning)
                if not ievent.nolog: logging.debug('ALERT %s %s job taking too long: %s seconds' % (descr, str(func), self.elapsed))
        except Exception, ex:
            handle_exception()
        #finally: lockmanager.release(getname(str(func)))
        self.working = False

class LongRunner(Runner):

    def handle(self, speed, args):
        """ schedule a bot command. """
        try:
            descr, func, bot, ievent = args
            self.starttime = time.time()
            #lockmanager.acquire(getname(str(func)))
            #self.nowrunning = getname(func)
            if not ievent.nolog: logging.debug("long event handler is %s" % str(func))
            self.working = True
            func(bot, ievent)
            self.elapsed = time.time() - self.starttime
            if self.elapsed < 1 and self.nowrunning not in self.shortrunning: self.shortrunning.append(self.nowrunning)
        except Exception, ex:
            handle_exception()
        #finally: lockmanager.release(getname(str(func)))
        self.working = False
        logging.debug("long finished - %s" % self.nowrunning)

## Runners class

class Runners(object):

    """ runners is a collection of runner objects. """

    def __init__(self, name, max=100, runnertype=Runner, doready=True):
        self.name = name
        self.max = max
        self.runners = []
        self.runnertype = runnertype
        self.doready = doready

    def names(self):
        return [getname(runner.name) for runner in self.runners]

    def size(self):
        qsize = [runner.queue.qsize() for runner in self.runners]
        return "%s/%s" % (qsize, len(self.runners))

    def runnersizes(self):
        """ return sizes of runner objects. """
        result = []
        for runner in self.runners: result.append("%s - %s" % (runner.queue.qsize(), runner.name))
        return result

    def stop(self):
        """ stop runners. """
        for runner in self.runners: runner.stop()

    def start(self):
        """ overload this if needed. """
        pass
 
    def put(self, speed, *data):
        """ put a job on a free runner. """
        for runner in self.runners:
            if runner.queue.empty():
                runner.put(speed, *data)
                return
        if self.runners: self.cleanup()
        runner = self.makenew()
        runner.put(speed, *data)
              
    def running(self):
        """ return list of running jobs. """
        result = []
        for runner in self.runners:
            if runner.working: result.append(runner.nowrunning)
        return result

    def makenew(self):
        """ create a new runner. """
        runner = None
        if len(self.runners) < self.max:
            runner = self.runnertype(self.name + "-" + str(len(self.runners)))
            runner.start()
            self.runners.append(runner)
        else: runner = random.choice(self.runners)
        return runner

    def cleanup(self):
        """ clean up idle runners. """
        r = []
        for runner in self.runners:
            if runner.queue.empty(): r.append(runner)
        if not r: return
        for runner in r: runner.stop()
        for runner in r:
            try: self.runners.remove(runner)
            except ValueError: pass
        logging.debug("%s - cleaned %s" %  (self.name, [item.name for item in r]))
        logging.debug("%s - now running: %s" % (self.name, self.size()))
        
## show runner status

def runner_status():
    print cmndrunner.runnersizes()
    print callbackrunner.runnersizes()


## global runners

cmndrunner = defaultrunner = Runners("default", 100, BotEventRunner) 
longrunner = Runners("long", 80, LongRunner)
callbackrunner = Runners("callback", 30, BotEventRunner)
waitrunner = Runners("wait", 20, BotEventRunner)
apirunner = Runners("api", 10, BotEventRunner)

## cleanup 

def runnercleanup(bot, event):
    cmndrunner.cleanup()
    longrunner.cleanup()
    callbackrunner.cleanup()
    waitrunner.cleanup()
    apirunner.cleanup()

callbacks.add("TICK60", runnercleanup)

def size():
    return "cmnd: %s - callbacks: %s - wait: %s - long: %s - api: %s" % (cmndrunner.size(), callbackrunner.size(), waitrunner.size(), longrunner.size(), apirunner.size())
