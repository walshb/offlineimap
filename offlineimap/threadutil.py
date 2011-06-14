# Copyright (C) 2002, 2003 John Goerzen
# Thread support module
# <jgoerzen@complete.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

from threading import Lock, Thread, BoundedSemaphore
from Queue import Queue, Empty
from thread import get_ident	# python < 2.6 support
from offlineimap.ui import getglobalui

######################################################################
# General utilities
######################################################################

def semaphorereset(semaphore, originalstate):
    """Wait until the semaphore gets back to its original state -- all acquired
    resources released."""
    for i in range(originalstate):
        semaphore.acquire()
    # Now release these.
    for i in range(originalstate):
        semaphore.release()

class ThreadQueue(Queue):
    """Beefed up Queue that allows to wait until all threads terminated

    It overrides join(), and blocks until all containing threads have terminated
    before returning"""
    def join(self):
        """Wait until all containing threads have terminated

        :meth:`join` is not threading safe, but it is not needed as long as no
        one calls :meth:`get` from other threads."""
        while not self.empty():
            thread = self.get()
            thread.join()
            # notify as task_done whenever a thread as finished
            self.task_done()
            

######################################################################
# Exit-notify threads
######################################################################
class ExitNotifyThread(Thread):
    """Alert 'monitor' if a thread has exits

    This class is designed to alert a "monitor" to the fact that a
    thread has exited and to provide for the ability for it to find out
    why."""
    profiledir = None
    """class variable that enables perf profiling if set to a dir"""

    def run(self):
        self.threadid = get_ident()
        try:
            if not self.profiledir:          # normal case
                Thread.run(self)
            else:                       # in profile mode
                try:
                    import cProfile as profile
                except ImportError:
                    import profile
                prof = profile.Profile()
                try:
                    prof = prof.runctx("Thread.run(self)", globals(), locals())
                except SystemExit:
                    pass
                prof.dump_stats("%s/%s_%s.prof" %\
                               (self.profiledir, self.threadid, self.getName()))
        finally:
            getglobalui().threadExited(self)

######################################################################
# Instance-limited threads
######################################################################

instancelimitedsems = {}
instancelimitedlock = Lock()

def initInstanceLimit(instancename, instancemax):
    """Initialize the instance-limited thread implementation to permit
    up to intancemax threads with the given instancename."""
    instancelimitedlock.acquire()
    if not instancelimitedsems.has_key(instancename):
        instancelimitedsems[instancename] = BoundedSemaphore(instancemax)
    instancelimitedlock.release()

class InstanceLimitedThread(ExitNotifyThread):
    def __init__(self, instancename, *args, **kwargs):
        self.instancename = instancename
                                                   
        apply(ExitNotifyThread.__init__, (self,) + args, kwargs)

    def start(self):
        instancelimitedsems[self.instancename].acquire()
        ExitNotifyThread.start(self)
        
    def run(self):
        try:
            ExitNotifyThread.run(self)
        finally:
            if instancelimitedsems and instancelimitedsems[self.instancename]:
                instancelimitedsems[self.instancename].release()
