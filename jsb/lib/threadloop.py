# jsb/threadloop.py
#
#

""" class to implement start/stoppable threads. """

# lib imports

import logging
import queue
import time

from jsb.utils.exception import handle_exception

from .threads import getname, start_new_thread

# basic imports


# ThreadLoop class


class ThreadLoop(object):

    """implement startable/stoppable threads."""

    def __init__(self, name="", queue_arg=None):
        self.name = name
        self.stopped = False
        self.running = False
        self.outs = []
        if queue_arg:
            self.queue = queue_arg
        else:
            self.queue = queue.PriorityQueue()
        self.nowrunning = "none"

    def _loop(self):
        """the threadloops loop."""
        logging.warn("starting %s" % getname(self))
        self.running = True
        nrempty = 0
        while not self.stopped:
            try:
                (speed, data) = self.queue.get()
            except IndexError:
                if self.stopped:
                    break
                time.sleep(0.1)
                continue
            if self.stopped:
                break
            if not data:
                break
            try:
                self.handle(*data)
            except Exception as ex:
                handle_exception()
        self.running = False
        logging.warn("stopping %s" % getname(self))

    def put(self, speed, *data):
        """put data on task queue."""
        self.queue.put((speed, data))

    def start(self):
        """start the thread."""
        if not self.running and not self.stopped:
            return start_new_thread(self._loop, ())

    def stop(self):
        """stop the thread."""
        self.stopped = True
        self.running = False
        self.put(0, None)

    def handle(self, *args, **kwargs):
        """overload this."""


# RunnerLoop class


class RunnerLoop(ThreadLoop):

    """dedicated threadloop for bot commands/callbacks."""

    def put(self, speed, *data):
        """put data on task queue."""
        self.queue.put((speed, data))

    def _loop(self):
        """runner loop."""
        logging.debug("%s - starting threadloop" % self.name)
        self.running = True
        while not self.stopped:
            try:
                speed, data = self.queue.get()
                if self.stopped:
                    break
                if not data:
                    break
                self.nowrunning = getname(data[1])
                self.handle(speed, data)
            except IndexError:
                time.sleep(0.1)
                continue
            except Exception as ex:
                handle_exception()
            # self.nowrunning = getname(data[1]) + "-done"
        self.running = False
        logging.debug("%s - stopping threadloop" % self.name)


class TimedLoop(ThreadLoop):

    """threadloop that sleeps x seconds before executing."""

    def __init__(self, name, sleepsec=300, *args, **kwargs):
        ThreadLoop.__init__(self, name, *args, **kwargs)
        self.sleepsec = sleepsec

    def _loop(self):
        """timed loop. sleep a while."""
        logging.warn(
            "%s - starting timedloop (%s seconds)" % (self.name, self.sleepsec)
        )
        self.stopped = False
        self.running = True
        while not self.stopped:
            time.sleep(self.sleepsec)
            if self.stopped:
                break
            try:
                self.handle()
            except Exception as ex:
                handle_exception()
        self.running = False
        logging.warn("%s - stopping timedloop" % self.name)
