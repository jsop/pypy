from pypy.rlib import _rffi_stacklet as _c
from pypy.rpython.lltypesystem import lltype, llmemory

DEBUG = False


class StackletThread(object):

    def __init__(self, config):
        self._gcrootfinder = _getgcrootfinder(config)
        self._thrd = _c.newthread()
        if not self._thrd:
            raise MemoryError
        self._thrd_deleter = StackletThreadDeleter(self._thrd)
        if DEBUG:
            assert debug.sthread is None, "multithread debug support missing"
            debug.sthread = self

    def new(self, callback, arg=llmemory.NULL):
        if DEBUG:
            callback = _debug_wrapper(callback)
        h = self._gcrootfinder.new(self, callback, arg)
        if DEBUG:
            debug.add(h)
        return h
    new._annspecialcase_ = 'specialize:arg(1)'

    def switch(self, stacklet):
        if DEBUG:
            debug.remove(stacklet)
        h = self._gcrootfinder.switch(self, stacklet)
        if DEBUG:
            debug.add(h)
        return h

    def destroy(self, stacklet):
        if DEBUG:
            debug.remove(stacklet)
        self._gcrootfinder.destroy(self, stacklet)

    def is_empty_handle(self, stacklet):
        # note that "being an empty handle" and being equal to
        # "get_null_handle()" may be the same, or not; don't rely on it
        return self._gcrootfinder.is_empty_handle(stacklet)

    def get_null_handle(self):
        return self._gcrootfinder.get_null_handle()


class StackletThreadDeleter(object):
    # quick hack: the __del__ is on another object, so that
    # if the main StackletThread ends up in random circular
    # references, on pypy deletethread() is only called
    # when all that circular reference mess is gone.
    def __init__(self, thrd):
        self._thrd = thrd
    def __del__(self):
        thrd = self._thrd
        if thrd:
            self._thrd = lltype.nullptr(_c.thread_handle.TO)
            _c.deletethread(thrd)

# ____________________________________________________________

def _getgcrootfinder(config):
    if (config is None or
        config.translation.gc in ('ref', 'boehm', 'none')):   # for tests
        gcrootfinder = 'n/a'
    else:
        gcrootfinder = config.translation.gcrootfinder
    gcrootfinder = gcrootfinder.replace('/', '_')
    module = __import__('pypy.rlib._stacklet_%s' % gcrootfinder,
                        None, None, ['__doc__'])
    return module.gcrootfinder
_getgcrootfinder._annspecialcase_ = 'specialize:memo'


class StackletDebugError(Exception):
    pass

class Debug(object):
    def __init__(self):
        self.sthread = None
        self.active = []
    def _freeze_(self):
        self.__init__()
        return False
    def add(self, h):
        if not self.sthread.is_empty_handle(h):
            self.active.append(h)
    def remove(self, h):
        try:
            i = self.active.index(h)
        except ValueError:
            raise StackletDebugError
        del self.active[i]
debug = Debug()

def _debug_wrapper(callback):
    def wrapper(h, arg):
        debug.add(h)
        h = callback(h, arg)
        debug.remove(h)
        return h
    return wrapper
_debug_wrapper._annspecialcase_ = 'specialize:memo'
