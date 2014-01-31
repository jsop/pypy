import py
from pypy.interpreter.baseobjspace import W_Root
from pypy.interpreter.error import OperationError
from pypy.interpreter.gateway import interp2app, ObjSpace
from pypy.interpreter.typedef import TypeDef
from rpython.rlib import jit
from rpython.rlib.rshrinklist import AbstractShrinkList
from rpython.rlib.objectmodel import specialize
from rpython.rlib.rweakref import dead_ref
import weakref


class WRefShrinkList(AbstractShrinkList):
    def must_keep(self, wref):
        return wref() is not None


class WeakrefLifeline(W_Root):
    cached_weakref  = None
    cached_proxy    = None
    other_refs_weak = None

    def __init__(self, space):
        self.space = space

    def append_wref_to(self, w_ref):
        if self.other_refs_weak is None:
            self.other_refs_weak = WRefShrinkList()
        self.other_refs_weak.append(weakref.ref(w_ref))

    @specialize.arg(1)
    def traverse(self, callback, arg=None):
        if self.cached_weakref is not None:
            arg = callback(self, self.cached_weakref, arg)
        if self.cached_proxy is not None:
            arg = callback(self, self.cached_proxy, arg)
        if self.other_refs_weak is not None:
            for ref_w_ref in self.other_refs_weak.items():
                arg = callback(self, ref_w_ref, arg)
        return arg

    def _clear_wref(self, wref, _):
        w_ref = wref()
        if w_ref is not None:
            w_ref.clear()

    def clear_all_weakrefs(self):
        """Clear all weakrefs.  This is called when an app-level object has
        a __del__, just before the app-level __del__ method is called.
        """
        self.traverse(WeakrefLifeline._clear_wref)
        # Note that for no particular reason other than convenience,
        # weakref callbacks are not invoked eagerly here.  They are
        # invoked by self.__del__() anyway.

    @jit.dont_look_inside
    def get_or_make_weakref(self, w_subtype, w_obj):
        space = self.space
        w_weakreftype = space.gettypeobject(W_Weakref.typedef)
        #
        if space.is_w(w_weakreftype, w_subtype):
            if self.cached_weakref is not None:
                w_cached = self.cached_weakref()
                if w_cached is not None:
                    return w_cached
            w_ref = W_Weakref(space, w_obj, None)
            self.cached_weakref = weakref.ref(w_ref)
        else:
            # subclass: cannot cache
            w_ref = space.allocate_instance(W_Weakref, w_subtype)
            W_Weakref.__init__(w_ref, space, w_obj, None)
            self.append_wref_to(w_ref)
        return w_ref

    @jit.dont_look_inside
    def get_or_make_proxy(self, w_obj):
        space = self.space
        if self.cached_proxy is not None:
            w_cached = self.cached_proxy()
            if w_cached is not None:
                return w_cached
        if space.is_true(space.callable(w_obj)):
            w_proxy = W_CallableProxy(space, w_obj, None)
        else:
            w_proxy = W_Proxy(space, w_obj, None)
        self.cached_proxy = weakref.ref(w_proxy)
        return w_proxy

    def get_any_weakref(self, space):
        if self.cached_weakref is not None:
            w_ref = self.cached_weakref()
            if w_ref is not None:
                return w_ref
        if self.other_refs_weak is not None:
            w_weakreftype = space.gettypeobject(W_Weakref.typedef)
            for wref in self.other_refs_weak.items():
                w_ref = wref()
                if (w_ref is not None and space.isinstance_w(w_ref, w_weakreftype)):
                    return w_ref
        return space.w_None


class WeakrefLifelineWithCallbacks(WeakrefLifeline):

    def __init__(self, space, oldlifeline=None):
        self.space = space
        if oldlifeline is not None:
            self.cached_weakref = oldlifeline.cached_weakref
            self.cached_proxy = oldlifeline.cached_proxy
            self.other_refs_weak = oldlifeline.other_refs_weak

    def __del__(self):
        """This runs when the interp-level object goes away, and allows
        its lifeline to go away.  The purpose of this is to activate the
        callbacks even if there is no __del__ method on the interp-level
        W_Root subclass implementing the object.
        """
        if self.other_refs_weak is None:
            return
        items = self.other_refs_weak.items()
        for i in range(len(items)-1, -1, -1):
            w_ref = items[i]()
            if w_ref is not None and w_ref.w_callable is not None:
                w_ref.enqueue_for_destruction(self.space,
                                              W_WeakrefBase.activate_callback,
                                              'weakref callback of ')

    @jit.dont_look_inside
    def make_weakref_with_callback(self, w_subtype, w_obj, w_callable):
        space = self.space
        w_ref = space.allocate_instance(W_Weakref, w_subtype)
        W_Weakref.__init__(w_ref, space, w_obj, w_callable)
        self.append_wref_to(w_ref)
        return w_ref

    @jit.dont_look_inside
    def make_proxy_with_callback(self, w_obj, w_callable):
        space = self.space
        if space.is_true(space.callable(w_obj)):
            w_proxy = W_CallableProxy(space, w_obj, w_callable)
        else:
            w_proxy = W_Proxy(space, w_obj, w_callable)
        self.append_wref_to(w_proxy)
        return w_proxy

# ____________________________________________________________


class W_WeakrefBase(W_Root):
    def __init__(w_self, space, w_obj, w_callable):
        assert w_callable is not space.w_None    # should be really None
        w_self.space = space
        assert w_obj is not None
        w_self.w_obj_weak = weakref.ref(w_obj)
        w_self.w_callable = w_callable

    @jit.dont_look_inside
    def dereference(self):
        w_obj = self.w_obj_weak()
        return w_obj

    def clear(self):
        self.w_obj_weak = dead_ref

    def activate_callback(w_self):
        assert isinstance(w_self, W_WeakrefBase)
        w_self.space.call_function(w_self.w_callable, w_self)

    def descr__repr__(self, space):
        w_obj = self.dereference()
        if w_obj is None:
            state = '; dead'
        else:
            typename = space.type(w_obj).getname(space)
            objname = w_obj.getname(space)
            if objname and objname != '?':
                state = "; to '%s' (%s)" % (typename, objname)
            else:
                state = "; to '%s'" % (typename,)
        return self.getrepr(space, self.typedef.name, state)


class W_Weakref(W_WeakrefBase):
    def __init__(w_self, space, w_obj, w_callable):
        W_WeakrefBase.__init__(w_self, space, w_obj, w_callable)
        w_self.w_hash = None

    def descr__init__weakref(self, space, w_obj, w_callable=None,
                             __args__=None):
        if __args__.arguments_w:
            raise OperationError(space.w_TypeError, space.wrap(
                "__init__ expected at most 2 arguments"))

    def descr_hash(self):
        if self.w_hash is not None:
            return self.w_hash
        w_obj = self.dereference()
        if w_obj is None:
            raise OperationError(self.space.w_TypeError,
                                 self.space.wrap("weak object has gone away"))
        self.w_hash = self.space.hash(w_obj)
        return self.w_hash

    def descr_call(self):
        w_obj = self.dereference()
        if w_obj is None:
            return self.space.w_None
        return w_obj

    def descr__eq__(self, space, w_ref2):
        if not isinstance(w_ref2, W_Weakref):
            return space.w_NotImplemented
        ref1 = self
        ref2 = w_ref2
        w_obj1 = ref1.dereference()
        w_obj2 = ref2.dereference()
        if w_obj1 is None or w_obj2 is None:
            return space.is_(ref1, ref2)
        return space.eq(w_obj1, w_obj2)

    def descr__ne__(self, space, w_ref2):
        return space.not_(space.eq(self, w_ref2))

def getlifeline(space, w_obj):
    lifeline = w_obj.getweakref()
    if lifeline is None:
        lifeline = WeakrefLifeline(space)
        w_obj.setweakref(space, lifeline)
    return lifeline

def getlifelinewithcallbacks(space, w_obj):
    lifeline = w_obj.getweakref()
    if not isinstance(lifeline, WeakrefLifelineWithCallbacks):  # or None
        oldlifeline = lifeline
        lifeline = WeakrefLifelineWithCallbacks(space, oldlifeline)
        w_obj.setweakref(space, lifeline)
    return lifeline


def get_or_make_weakref(space, w_subtype, w_obj):
    return getlifeline(space, w_obj).get_or_make_weakref(w_subtype, w_obj)


def make_weakref_with_callback(space, w_subtype, w_obj, w_callable):
    lifeline = getlifelinewithcallbacks(space, w_obj)
    return lifeline.make_weakref_with_callback(w_subtype, w_obj, w_callable)


def descr__new__weakref(space, w_subtype, w_obj, w_callable=None,
                        __args__=None):
    if __args__.arguments_w:
        raise OperationError(space.w_TypeError, space.wrap(
            "__new__ expected at most 2 arguments"))
    if space.is_none(w_callable):
        return get_or_make_weakref(space, w_subtype, w_obj)
    else:
        return make_weakref_with_callback(space, w_subtype, w_obj, w_callable)

W_Weakref.typedef = TypeDef("weakref",
    __doc__ = """A weak reference to an object 'obj'.  A 'callback' can be given,
which is called with 'obj' as an argument when it is about to be finalized.""",
    __new__ = interp2app(descr__new__weakref),
    __init__ = interp2app(W_Weakref.descr__init__weakref),
    __eq__ = interp2app(W_Weakref.descr__eq__),
    __ne__ = interp2app(W_Weakref.descr__ne__),
    __hash__ = interp2app(W_Weakref.descr_hash),
    __call__ = interp2app(W_Weakref.descr_call),
    __repr__ = interp2app(W_WeakrefBase.descr__repr__),
)


def _weakref_count(lifeline, wref, count):
    if wref() is not None:
        count += 1
    return count

def getweakrefcount(space, w_obj):
    """Return the number of weak references to 'obj'."""
    lifeline = w_obj.getweakref()
    if lifeline is None:
        return space.wrap(0)
    else:
        result = lifeline.traverse(_weakref_count, 0)
        return space.wrap(result)

def _get_weakrefs(lifeline, wref, result):
    w_ref = wref()
    if w_ref is not None:
        result.append(w_ref)
    return result

def getweakrefs(space, w_obj):
    """Return a list of all weak reference objects that point to 'obj'."""
    result = []
    lifeline = w_obj.getweakref()
    if lifeline is not None:
        lifeline.traverse(_get_weakrefs, result)
    return space.newlist(result)

#_________________________________________________________________
# Proxy

class W_Proxy(W_WeakrefBase):
    def descr__hash__(self, space):
        raise OperationError(space.w_TypeError,
                             space.wrap("unhashable type"))

class W_CallableProxy(W_Proxy):
    def descr__call__(self, space, __args__):
        w_obj = force(space, self)
        return space.call_args(w_obj, __args__)


def get_or_make_proxy(space, w_obj):
    return getlifeline(space, w_obj).get_or_make_proxy(w_obj)


def make_proxy_with_callback(space, w_obj, w_callable):
    lifeline = getlifelinewithcallbacks(space, w_obj)
    return lifeline.make_proxy_with_callback(w_obj, w_callable)


def proxy(space, w_obj, w_callable=None):
    """Create a proxy object that weakly references 'obj'.
'callback', if given, is called with the proxy as an argument when 'obj'
is about to be finalized."""
    if space.is_none(w_callable):
        return get_or_make_proxy(space, w_obj)
    else:
        return make_proxy_with_callback(space, w_obj, w_callable)

def descr__new__proxy(space, w_subtype, w_obj, w_callable=None):
    raise OperationError(
        space.w_TypeError,
        space.wrap("cannot create 'weakproxy' instances"))

def descr__new__callableproxy(space, w_subtype, w_obj, w_callable=None):
    raise OperationError(
        space.w_TypeError,
        space.wrap("cannot create 'weakcallableproxy' instances"))


def force(space, proxy):
    if not isinstance(proxy, W_Proxy):
        return proxy
    w_obj = proxy.dereference()
    if w_obj is None:
        raise OperationError(
            space.w_ReferenceError,
            space.wrap("weakly referenced object no longer exists"))
    return w_obj

proxy_typedef_dict = {}
callable_proxy_typedef_dict = {}
special_ops = {'repr': True, 'userdel': True, 'hash': True}

for opname, _, arity, special_methods in ObjSpace.MethodTable:
    if opname in special_ops or not special_methods:
        continue
    nonspaceargs =  ", ".join(["w_obj%s" % i for i in range(arity)])
    code = "def func(space, %s):\n    '''%s'''\n" % (nonspaceargs, opname)
    assert arity >= len(special_methods)
    forcing_count = len(special_methods)
    if opname.startswith('inplace_'):
        assert arity == 2
        forcing_count = arity
    for i in range(forcing_count):
        code += "    w_obj%s = force(space, w_obj%s)\n" % (i, i)
    code += "    return space.%s(%s)" % (opname, nonspaceargs)
    exec py.code.Source(code).compile()

    func.func_name = opname
    for special_method in special_methods:
        proxy_typedef_dict[special_method] = interp2app(func)
        callable_proxy_typedef_dict[special_method] = interp2app(func)

# __unicode__ is not yet a space operation
def proxy_unicode(space, w_obj):
    w_obj = force(space, w_obj)
    return space.call_method(w_obj, '__unicode__')
proxy_typedef_dict['__unicode__'] = interp2app(proxy_unicode)
callable_proxy_typedef_dict['__unicode__'] = interp2app(proxy_unicode)


W_Proxy.typedef = TypeDef("weakproxy",
    __new__ = interp2app(descr__new__proxy),
    __hash__ = interp2app(W_Proxy.descr__hash__),
    __repr__ = interp2app(W_WeakrefBase.descr__repr__),
    **proxy_typedef_dict)
W_Proxy.typedef.acceptable_as_base_class = False

W_CallableProxy.typedef = TypeDef("weakcallableproxy",
    __new__ = interp2app(descr__new__callableproxy),
    __hash__ = interp2app(W_Proxy.descr__hash__),
    __repr__ = interp2app(W_WeakrefBase.descr__repr__),
    __call__ = interp2app(W_CallableProxy.descr__call__),
    **callable_proxy_typedef_dict)
W_CallableProxy.typedef.acceptable_as_base_class = False
