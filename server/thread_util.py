'''
Utilities for running threaded workers in web request handlers.

:copyright: Peter Parente 2010
:license: BSD
'''
import tornado.web
from tornado import ioloop
import os
import fcntl
import sys
import thread
import time
import copy
import logging
from threading import Thread, Lock, Event, local
from Queue import Queue, Empty

class AsyncThreadPool(object):
    '''
    Provide a pool of N threads that executes tasks and issues callbacks with 
    the results. Allows blocking code to run ``asynchronously'' in the Tornado 
    IO loop using threads and a pipe. This only works if the threads release 
    the GIL which is common enough to be useful.
    
    Adapted from a gist by Marius A. Eriksen (http://gist.github.com/283103).
    
    :ivar _io_loop:
    :ivar _reader:
    :ivar _writer:
    :ivar _queue:
    :ivar _done_queue:
    :ivar _threads:
    :ivar _local:
    :ivar _running:
    :ivar _lock:
    :ivar _join_event:
    '''
    MONITOR_INTERVAL_SECONDS             = 15
    MONITOR_STUCK_THREADS_MULTIPLIER     = 0.5
    MONITOR_TRIGGER_STUCK_THREAD_SECONDS = 30

    def __init__(self, nthreads=1):
        '''
        :param nthreads: Number of threads to create in the pool
        :type nthreads: int
        '''
        # ref to the ioloop
        self._io_loop = ioloop.IOLoop.instance()

        # read/write pipes for ioloop notifications
        rfd, wfd = os.pipe()
        for fd in [rfd, wfd]:
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._reader = os.fdopen(rfd, 'r', 0)
        self._writer = os.fdopen(wfd, 'w', 0)
        self._io_loop.add_handler(
            rfd, self._handle_ioloop_event, self._io_loop.READ)

        # task and complete queue
        self._queue = Queue()
        self._done_queue = Queue()

        # thread pool
        self._threads = []
        # info about thread workers
        self._running = {}
        # locks
        self._lock = Lock()
        self._join_event = Event()

        # create the thread pool
        for i in range(nthreads):
            t = Thread(target=self._loop)
            t.setDaemon(True)
            t.start()
            self._threads.append(t)

        # create a monitor thread
        t = Thread(target=self._monitor)
        t.setDaemon(True)
        t.start()

    def _handle_ioloop_event(self, fd, events):
        '''
        Performs all callbacks when notified by the ioloop.
        
        :param fd:
        :param events:
        '''
        self._reader.read()
        self._flush_callback_queue()

    def _loop(self):
        '''
        Runs a worker thread loop until a None task is received.
        '''
        while True:
            item = self._queue.get()
            if item is None:
                # thread shutting down
                self._queue.task_done()
                return

            # get task info
            callback, fun, args, kwargs = item

            with self._lock:
                # track running thread info
                info = (time.time(), fun, args, kwargs)
                self._running[thread.get_ident()] = info

            try:
                # run the worker
                result = (fun(*args, **kwargs), None, None)
            except Exception, e:
                # provide exception info
                result = (None, e, sys.exc_info()[2])

            with self._lock:
                # stop tracking running thread
                del self._running[thread.get_ident()]

            if callback is not None:
                # put the results on the done queue 
                # notify the eventloop by writing to the pipe
                self._done_queue.put((callback, result))
                self._writer.write('.')

            self._queue.task_done()

    def _flush_callback_queue(self):
        '''
        Perform all callbacks for completed workers.
        '''
        while True:
            try:
                callback, result = self._done_queue.get(False)
                callback(*result)
            except Empty:
                return

    def _monitor(self):
        '''
        Runs a monitor thread until a join event is set.
        '''
        while not self._join_event.is_set():
            self._commit_suicide_if_threads_are_stuck()
            self._join_event.wait(self.MONITOR_INTERVAL_SECONDS)

    def _commit_suicide_if_threads_are_stuck(self):
        '''
        Kills the whole server if too many threads are stuck.
        
        .. todo:: probably want a callback instead of just dying
        '''
        with self._lock:
            num_max_stuck_threads = \
                len(self._threads) * self.MONITOR_STUCK_THREADS_MULTIPLIER

            now = time.time()
            elapseds = [now - t for t, _, _, _ in self._running.values()]
            elapseds = filter(
                lambda d: d > self.MONITOR_TRIGGER_STUCK_THREAD_SECONDS,
                elapseds)
            logging.debug('monitor: thread elapseds = %r' % elapseds)
            nelapsed = len(elapseds)
            if nelapsed:
                logging.info('monitor: %d threads are stuck' % nelapsed)
            if nelapsed >= num_max_stuck_threads:
                logging.info('monitor: too many threads are stuck, '
                             'committing suicide')
                # hard exit.
                os._exit(1)

    def join(self):
        '''
        Join the worker threads & queue, ensuring that all tasks
        are completed. The object is effectively dead after this call.
        '''
        # issue the join on the queue to block until all items processed
        self._queue.join()
        # set the join event to notify the monitor
        self._join_event.set()
        # notify all worker threads to shutdown
        for _ in self._threads:
            self._queue.put(None)
        # join all worker threads
        while self._threads:
            self._threads.pop().join()
        # disconnect from the ioloop
        self._io_loop.remove_handler(self._reader.fileno())
        # perform all remaining callbacks
        self._flush_callback_queue()
        # close the read/write pipes
        self._reader.close()
        self._writer.close()

    def __call__(self, callback, worker, *args, **kwargs):
        '''
        Queue a worker to run.
        
        :param callback:
        :param worker:
        :param args:
        :param kwargs:
        '''
        self._queue.put((callback, worker, args, kwargs))

    def get_status(self):
        '''
        Gets the status of all running threads. Useful for debugging.
        
        :rtype: str
        '''
        now = time.time()
        with POOL._lock:
            running = copy.copy(POOL._running.items())
        s = '# ident'.ljust(20) + 'invocation' + '\n'
        for ident, (begintime, fun, args, kwargs) in running:
            s += str(ident).ljust(20)
            args = map(repr, args) + \
                   ['%s=%r' % (k, v) for k, v in kwargs.items()]
            s += '%s(%s)' % (fun.__name__, ', '.join(args))
            s += ' [for %fs]' % (now - begintime)
            s += '\n'
        return s
        
class ThreadPoolApplication(tornado.web.Application):
    '''
    Builds a thread pool during object construction.
    '''
    def __init__(self, *args, **kwargs):
        super(ThreadPoolApplication, self).__init__(*args, **kwargs)
        self.thread_pool = AsyncThreadPool(kwargs.get('thread_count'))

class ThreadedRequestHandler(tornado.web.RequestHandler):
    '''
    Provides convenience methods for using the thread pool.
    '''
    def run_async(self, callback, worker, *args, **kwargs):
        '''
        Runs a worker function in a thread and receives the result in a 
        callback.
        
        :param callback:
        :param worker:
        :param args:
        :param kwargs:
        '''
        cb = self.async_callback(callback)
        self.application.thread_pool(cb, worker, *args, **kwargs)