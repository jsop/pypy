"""Test date/time type.

This is a py.test conversion of the test cases in the CVS sandbox of
CPython.
"""
import autopath

import sys
import pickle
import cPickle

from pypy.appspace.datetime import MINYEAR, MAXYEAR
from pypy.appspace.datetime import timedelta
from pypy.appspace.datetime import tzinfo
from pypy.appspace.datetime import time
from pypy.appspace.datetime import date, datetime


# Before Python 2.3, proto=2 was taken as a synonym for proto=1.
pickle_choices = [(pickler, unpickler, proto)
                  for pickler in pickle, cPickle
                  for unpickler in pickle, cPickle
                  for proto in range(3)]
assert len(pickle_choices) == 2*2*3

# An arbitrary collection of objects of non-datetime types, for testing
# mixed-type comparisons.
OTHERSTUFF = (10, 10L, 34.5, "abc", {}, [], ())


#############################################################################
# module tests

class TestModule(object):

    def test_constants(self):
        from pypy.appspace import datetime
        assert datetime.MINYEAR == 1
        assert datetime.MAXYEAR == 9999

#############################################################################
# tzinfo tests

class FixedOffset(tzinfo):
    def __init__(self, offset, name, dstoffset=42):
        if isinstance(offset, int):
            offset = timedelta(minutes=offset)
        if isinstance(dstoffset, int):
            dstoffset = timedelta(minutes=dstoffset)
        self.__offset = offset
        self.__name = name
        self.__dstoffset = dstoffset
    def __repr__(self):
        return self.__name.lower()
    def utcoffset(self, dt):
        return self.__offset
    def tzname(self, dt):
        return self.__name
    def dst(self, dt):
        return self.__dstoffset

class PicklableFixedOffset(FixedOffset):
    def __init__(self, offset=None, name=None, dstoffset=None):
        FixedOffset.__init__(self, offset, name, dstoffset)

class TestTZInfo(object):

    def test_non_abstractness(self):
        # In order to allow subclasses to get pickled, the C implementation
        # wasn't able to get away with having __init__ raise
        # NotImplementedError.
        useless = tzinfo()
        dt = datetime.max
        raises(NotImplementedError, useless.tzname, dt)
        raises(NotImplementedError, useless.utcoffset, dt)
        raises(NotImplementedError, useless.dst, dt)

    def test_subclass_must_override(self):
        class NotEnough(tzinfo):
            def __init__(self, offset, name):
                self.__offset = offset
                self.__name = name
        assert issubclass(NotEnough, tzinfo)
        ne = NotEnough(3, "NotByALongShot")
        assert isinstance(ne, tzinfo)

        dt = datetime.now()
        raises(NotImplementedError, ne.tzname, dt)
        raises(NotImplementedError, ne.utcoffset, dt)
        raises(NotImplementedError, ne.dst, dt)

    def test_normal(self):
        fo = FixedOffset(3, "Three")
        assert isinstance(fo, tzinfo)
        for dt in datetime.now(), None:
            assert fo.utcoffset(dt) == timedelta(minutes=3)
            assert fo.tzname(dt) == "Three"
            assert fo.dst(dt) == timedelta(minutes=42)

    def test_pickling_base(self):
        # There's no point to pickling tzinfo objects on their own (they
        # carry no data), but they need to be picklable anyway else
        # concrete subclasses can't be pickled.
        orig = tzinfo.__new__(tzinfo)
        assert type(orig) is tzinfo
        for pickler, unpickler, proto in pickle_choices:
                green = pickler.dumps(orig, proto)
                derived = unpickler.loads(green)
                assert type(derived) is tzinfo

    def test_pickling_subclass(self):
        # Make sure we can pickle/unpickle an instance of a subclass.
        offset = timedelta(minutes=-300)
        orig = PicklableFixedOffset(offset, 'cookie')
        assert isinstance(orig, tzinfo)
        assert type(orig) is PicklableFixedOffset
        assert orig.utcoffset(None) == offset
        assert orig.tzname(None) == 'cookie'
        for pickler, unpickler, proto in pickle_choices:
                green = pickler.dumps(orig, proto)
                derived = unpickler.loads(green)
                assert isinstance(derived, tzinfo)
                assert type(derived) is PicklableFixedOffset
                assert derived.utcoffset(None) == offset
                assert derived.tzname(None) == 'cookie'

#############################################################################
# Base clase for testing a particular aspect of timedelta, time, date and
# datetime comparisons.

class HarmlessMixedComparison(object):
    # Test that __eq__ and __ne__ don't complain for mixed-type comparisons.

    # Subclasses must define 'theclass', and theclass(1, 1, 1) must be a
    # legit constructor.

    def test_harmless_mixed_comparison(self):
        me = self.theclass(1, 1, 1)

        assert not me == ()
        assert me != ()
        assert not () == me
        assert () != me

        assert me in [1, 20L, [], me]
        assert not me not in [1, 20L, [], me]

        assert [] in [me, 1, 20L, []]
        assert not [] not in [me, 1, 20L, []]

    def test_harmful_mixed_comparison(self):
        me = self.theclass(1, 1, 1)

        raises(TypeError, lambda: me < ())
        raises(TypeError, lambda: me <= ())
        raises(TypeError, lambda: me > ())
        raises(TypeError, lambda: me >= ())

        raises(TypeError, lambda: () < me)
        raises(TypeError, lambda: () <= me)
        raises(TypeError, lambda: () > me)
        raises(TypeError, lambda: () >= me)

        raises(TypeError, cmp, (), me)
        raises(TypeError, cmp, me, ())

#############################################################################
# timedelta tests

class TestTimeDelta(HarmlessMixedComparison):

    theclass = timedelta

    def test_constructor(self):
        td = timedelta

        # Check keyword args to constructor
        assert td() == td(weeks=0, days=0, hours=0, minutes=0, seconds=0,
                    milliseconds=0, microseconds=0)
        assert td(1) == td(days=1)
        assert td(0, 1) == td(seconds=1)
        assert td(0, 0, 1) == td(microseconds=1)
        assert td(weeks=1) == td(days=7)
        assert td(days=1) == td(hours=24)
        assert td(hours=1) == td(minutes=60)
        assert td(minutes=1) == td(seconds=60)
        assert td(seconds=1) == td(milliseconds=1000)
        assert td(milliseconds=1) == td(microseconds=1000)

        # Check float args to constructor
        assert td(weeks=1.0/7) == td(days=1)
        assert td(days=1.0/24) == td(hours=1)
        assert td(hours=1.0/60) == td(minutes=1)
        assert td(minutes=1.0/60) == td(seconds=1)
        assert td(seconds=0.001) == td(milliseconds=1)
        assert td(milliseconds=0.001) == td(microseconds=1)

    def test_computations(self):
        td = timedelta

        a = td(7) # One week
        b = td(0, 60) # One minute
        c = td(0, 0, 1000) # One millisecond
        assert a+b+c == td(7, 60, 1000)
        assert a-b == td(6, 24*3600 - 60)
        assert -a == td(-7)
        assert +a == td(7)
        assert -b == td(-1, 24*3600 - 60)
        assert -c == td(-1, 24*3600 - 1, 999000)
        assert abs(a) == a
        assert abs(-a) == a
        assert td(6, 24*3600) == a
        assert td(0, 0, 60*1000000) == b
        assert a*10 == td(70)
        assert a*10 == 10*a
        assert a*10L == 10*a
        assert b*10 == td(0, 600)
        assert 10*b == td(0, 600)
        assert b*10L == td(0, 600)
        assert c*10 == td(0, 0, 10000)
        assert 10*c == td(0, 0, 10000)
        assert c*10L == td(0, 0, 10000)
        assert a*-1 == -a
        assert b*-2 == -b-b
        assert c*-2 == -c+-c
        assert b*(60*24) == (b*60)*24
        assert b*(60*24) == (60*b)*24
        assert c*1000 == td(0, 1)
        assert 1000*c == td(0, 1)
        assert a//7 == td(1)
        assert b//10 == td(0, 6)
        assert c//1000 == td(0, 0, 1)
        assert a//10 == td(0, 7*24*360)
        assert a//3600000 == td(0, 0, 7*24*1000)

    def test_disallowed_computations(self):
        a = timedelta(42)

        # Add/sub ints, longs, floats should be illegal
        for i in 1, 1L, 1.0:
            raises(TypeError, lambda: a+i)
            raises(TypeError, lambda: a-i)
            raises(TypeError, lambda: i+a)
            raises(TypeError, lambda: i-a)

        # Mul/div by float isn't supported.
        x = 2.3
        raises(TypeError, lambda: a*x)
        raises(TypeError, lambda: x*a)
        raises(TypeError, lambda: a/x)
        raises(TypeError, lambda: x/a)
        raises(TypeError, lambda: a // x)
        raises(TypeError, lambda: x // a)

        # Divison of int by timedelta doesn't make sense.
        # Division by zero doesn't make sense.
        for zero in 0, 0L:
            raises(TypeError, lambda: zero // a)
            raises(ZeroDivisionError, lambda: a // zero)

    def test_basic_attributes(self):
        days, seconds, us = 1, 7, 31
        td = timedelta(days, seconds, us)
        assert td.days == days
        assert td.seconds == seconds
        assert td.microseconds == us

    def test_carries(self):
        t1 = timedelta(days=100,
                       weeks=-7,
                       hours=-24*(100-49),
                       minutes=-3,
                       seconds=12,
                       microseconds=(3*60 - 12) * 1e6 + 1)
        t2 = timedelta(microseconds=1)
        assert t1 == t2

    def test_hash_equality(self):
        t1 = timedelta(days=100,
                       weeks=-7,
                       hours=-24*(100-49),
                       minutes=-3,
                       seconds=12,
                       microseconds=(3*60 - 12) * 1000000)
        t2 = timedelta()
        assert hash(t1) == hash(t2)

        t1 += timedelta(weeks=7)
        t2 += timedelta(days=7*7)
        assert t1 == t2
        assert hash(t1) == hash(t2)

        d = {t1: 1}
        d[t2] = 2
        assert len(d) == 1
        assert d[t1] == 2

    def test_pickling(self):
        args = 12, 34, 56
        orig = timedelta(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

    def test_compare(self):
        t1 = timedelta(2, 3, 4)
        t2 = timedelta(2, 3, 4)
        assert t1 == t2
        assert t1 <= t2
        assert t1 >= t2
        assert not t1 != t2
        assert not t1 < t2
        assert not t1 > t2
        assert cmp(t1, t2) == 0
        assert cmp(t2, t1) == 0

        for args in (3, 3, 3), (2, 4, 4), (2, 3, 5):
            t2 = timedelta(*args)   # this is larger than t1
            assert t1 < t2
            assert t2 > t1
            assert t1 <= t2
            assert t2 >= t1
            assert t1 != t2
            assert t2 != t1
            assert not t1 == t2
            assert not t2 == t1
            assert not t1 > t2
            assert not t2 < t1
            assert not t1 >= t2
            assert not t2 <= t1
            assert cmp(t1, t2) == -1
            assert cmp(t2, t1) == 1

        for badarg in OTHERSTUFF:
            assert (t1 == badarg) == False
            assert (t1 != badarg) == True
            assert (badarg == t1) == False
            assert (badarg != t1) == True

            raises(TypeError, lambda: t1 <= badarg)
            raises(TypeError, lambda: t1 < badarg)
            raises(TypeError, lambda: t1 > badarg)
            raises(TypeError, lambda: t1 >= badarg)
            raises(TypeError, lambda: badarg <= t1)
            raises(TypeError, lambda: badarg < t1)
            raises(TypeError, lambda: badarg > t1)
            raises(TypeError, lambda: badarg >= t1)

    def test_str(self):
        td = timedelta

        assert str(td(1)) == "1 day, 0:00:00"
        assert str(td(-1)) == "-1 day, 0:00:00"
        assert str(td(2)) == "2 days, 0:00:00"
        assert str(td(-2)) == "-2 days, 0:00:00"

        assert str(td(hours=12, minutes=58, seconds=59)) == "12:58:59"
        assert str(td(hours=2, minutes=3, seconds=4)) == "2:03:04"
        assert str(td(weeks=-30, hours=23, minutes=12, seconds=34)) == (
           "-210 days, 23:12:34")

        assert str(td(milliseconds=1)) == "0:00:00.001000"
        assert str(td(microseconds=3)) == "0:00:00.000003"

        assert str(td(days=999999999, hours=23, minutes=59, seconds=59,
                   microseconds=999999)) == (
           "999999999 days, 23:59:59.999999")

    def test_roundtrip(self):
        for td in (timedelta(days=999999999, hours=23, minutes=59,
                             seconds=59, microseconds=999999),
                   timedelta(days=-999999999),
                   timedelta(days=1, seconds=2, microseconds=3)):

            # Verify td -> string -> td identity.
            s = repr(td)
            assert s.startswith('datetime.')
            s = s[9:]
            td2 = eval(s)
            assert td == td2

            # Verify identity via reconstructing from pieces.
            td2 = timedelta(td.days, td.seconds, td.microseconds)
            assert td == td2

    def test_resolution_info(self):
        assert isinstance(timedelta.min, timedelta)
        assert isinstance(timedelta.max, timedelta)
        assert isinstance(timedelta.resolution, timedelta)
        assert timedelta.max > timedelta.min
        assert timedelta.min == timedelta(-999999999)
        assert timedelta.max == timedelta(999999999, 24*3600-1, 1e6-1)
        assert timedelta.resolution == timedelta(0, 0, 1)

    def test_overflow(self):
        tiny = timedelta.resolution

        td = timedelta.min + tiny
        td -= tiny  # no problem
        raises(OverflowError, td.__sub__, tiny)
        raises(OverflowError, td.__add__, -tiny)

        td = timedelta.max - tiny
        td += tiny  # no problem
        raises(OverflowError, td.__add__, tiny)
        raises(OverflowError, td.__sub__, -tiny)

        raises(OverflowError, lambda: -timedelta.max)

    def test_microsecond_rounding(self):
        td = timedelta

        # Single-field rounding.
        assert td(milliseconds=0.4/1000) == td(0)    # rounds to 0
        assert td(milliseconds=-0.4/1000) == td(0)    # rounds to 0
        assert td(milliseconds=0.6/1000) == td(microseconds=1)
        assert td(milliseconds=-0.6/1000) == td(microseconds=-1)

        # Rounding due to contributions from more than one field.
        us_per_hour = 3600e6
        us_per_day = us_per_hour * 24
        assert td(days=.4/us_per_day) == td(0)
        assert td(hours=.2/us_per_hour) == td(0)
        assert td(days=.4/us_per_day, hours=.2/us_per_hour) == td(microseconds=1)

        assert td(days=-.4/us_per_day) == td(0)
        assert td(hours=-.2/us_per_hour) == td(0)
        assert td(days=-.4/us_per_day, hours=-.2/us_per_hour) == td(microseconds=-1)

    def test_massive_normalization(self):
        td = timedelta(microseconds=-1)
        assert (td.days, td.seconds, td.microseconds) == (
                         (-1, 24*3600-1, 999999))

    def test_bool(self):
        assert timedelta(1)
        assert timedelta(0, 1)
        assert timedelta(0, 0, 1)
        assert timedelta(microseconds=1)
        assert not timedelta(0)

#############################################################################
# date tests

class TestDateOnly(object):
    # Tests here won't pass if also run on datetime objects, so don't
    # subclass this to test datetimes too.

    def test_delta_non_days_ignored(self):
        dt = date(2000, 1, 2)
        delta = timedelta(days=1, hours=2, minutes=3, seconds=4,
                          microseconds=5)
        days = timedelta(delta.days)
        assert days == timedelta(1)

        dt2 = dt + delta
        assert dt2 == dt + days

        dt2 = delta + dt
        assert dt2 == dt + days

        dt2 = dt - delta
        assert dt2 == dt - days

        delta = -delta
        days = timedelta(delta.days)
        assert days == timedelta(-2)

        dt2 = dt + delta
        assert dt2 == dt + days

        dt2 = delta + dt
        assert dt2 == dt + days

        dt2 = dt - delta
        assert dt2 == dt - days

class TestDate(HarmlessMixedComparison):
    # Tests here should pass for both dates and datetimes, except for a
    # few tests that TestDateTime overrides.

    theclass = date

    def test_basic_attributes(self):
        dt = self.theclass(2002, 3, 1)
        assert dt.year == 2002
        assert dt.month == 3
        assert dt.day == 1

    def test_roundtrip(self):
        for dt in (self.theclass(1, 2, 3),
                   self.theclass.today()):
            # Verify dt -> string -> date identity.
            s = repr(dt)
            assert s.startswith('datetime.')
            s = s[9:]
            dt2 = eval(s)
            assert dt == dt2

            # Verify identity via reconstructing from pieces.
            dt2 = self.theclass(dt.year, dt.month, dt.day)
            assert dt == dt2

    def test_ordinal_conversions(self):
        # Check some fixed values.
        for y, m, d, n in [(1, 1, 1, 1),      # calendar origin
                           (1, 12, 31, 365),
                           (2, 1, 1, 366),
                           # first example from "Calendrical Calculations"
                           (1945, 11, 12, 710347)]:
            d = self.theclass(y, m, d)
            assert n == d.toordinal()
            fromord = self.theclass.fromordinal(n)
            assert d == fromord
            if hasattr(fromord, "hour"):
                # if we're checking something fancier than a date, verify
                # the extra fields have been zeroed out
                assert fromord.hour == 0
                assert fromord.minute == 0
                assert fromord.second == 0
                assert fromord.microsecond == 0

        # Check first and last days of year spottily across the whole
        # range of years supported.
        for year in xrange(MINYEAR, MAXYEAR+1, 7):
            # Verify (year, 1, 1) -> ordinal -> y, m, d is identity.
            d = self.theclass(year, 1, 1)
            n = d.toordinal()
            d2 = self.theclass.fromordinal(n)
            assert d == d2
            # Verify that moving back a day gets to the end of year-1.
            if year > 1:
                d = self.theclass.fromordinal(n-1)
                d2 = self.theclass(year-1, 12, 31)
                assert d == d2
                assert d2.toordinal() == n-1

        # Test every day in a leap-year and a non-leap year.
        dim = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        for year, isleap in (2000, True), (2002, False):
            n = self.theclass(year, 1, 1).toordinal()
            for month, maxday in zip(range(1, 13), dim):
                if month == 2 and isleap:
                    maxday += 1
                for day in range(1, maxday+1):
                    d = self.theclass(year, month, day)
                    assert d.toordinal() == n
                    assert d == self.theclass.fromordinal(n)
                    n += 1

    def test_extreme_ordinals(self):
        a = self.theclass.min
        a = self.theclass(a.year, a.month, a.day)  # get rid of time parts
        aord = a.toordinal()
        b = a.fromordinal(aord)
        assert a == b

        raises(ValueError, lambda: a.fromordinal(aord - 1))

        b = a + timedelta(days=1)
        assert b.toordinal() == aord + 1
        assert b == self.theclass.fromordinal(aord + 1)

        a = self.theclass.max
        a = self.theclass(a.year, a.month, a.day)  # get rid of time parts
        aord = a.toordinal()
        b = a.fromordinal(aord)
        assert a == b

        raises(ValueError, lambda: a.fromordinal(aord + 1))

        b = a - timedelta(days=1)
        assert b.toordinal() == aord - 1
        assert b == self.theclass.fromordinal(aord - 1)

    def test_bad_constructor_arguments(self):
        # bad years
        self.theclass(MINYEAR, 1, 1)  # no exception
        self.theclass(MAXYEAR, 1, 1)  # no exception
        raises(ValueError, self.theclass, MINYEAR-1, 1, 1)
        raises(ValueError, self.theclass, MAXYEAR+1, 1, 1)
        # bad months
        self.theclass(2000, 1, 1)    # no exception
        self.theclass(2000, 12, 1)   # no exception
        raises(ValueError, self.theclass, 2000, 0, 1)
        raises(ValueError, self.theclass, 2000, 13, 1)
        # bad days
        self.theclass(2000, 2, 29)   # no exception
        self.theclass(2004, 2, 29)   # no exception
        self.theclass(2400, 2, 29)   # no exception
        raises(ValueError, self.theclass, 2000, 2, 30)
        raises(ValueError, self.theclass, 2001, 2, 29)
        raises(ValueError, self.theclass, 2100, 2, 29)
        raises(ValueError, self.theclass, 1900, 2, 29)
        raises(ValueError, self.theclass, 2000, 1, 0)
        raises(ValueError, self.theclass, 2000, 1, 32)

    def test_hash_equality(self):
        d = self.theclass(2000, 12, 31)
        # same thing
        e = self.theclass(2000, 12, 31)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

        d = self.theclass(2001,  1,  1)
        # same thing
        e = self.theclass(2001,  1,  1)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

    def test_computations(self):
        a = self.theclass(2002, 1, 31)
        b = self.theclass(1956, 1, 31)

        diff = a-b
        assert diff.days == 46*365 + len(range(1956, 2002, 4))
        assert diff.seconds == 0
        assert diff.microseconds == 0

        day = timedelta(1)
        week = timedelta(7)
        a = self.theclass(2002, 3, 2)
        assert a + day == self.theclass(2002, 3, 3)
        assert day + a == self.theclass(2002, 3, 3)
        assert a - day == self.theclass(2002, 3, 1)
        assert -day + a == self.theclass(2002, 3, 1)
        assert a + week == self.theclass(2002, 3, 9)
        assert a - week == self.theclass(2002, 2, 23)
        assert a + 52*week == self.theclass(2003, 3, 1)
        assert a - 52*week == self.theclass(2001, 3, 3)
        assert (a + week) - a == week
        assert (a + day) - a == day
        assert (a - week) - a == -week
        assert (a - day) - a == -day
        assert a - (a + week) == -week
        assert a - (a + day) == -day
        assert a - (a - week) == week
        assert a - (a - day) == day

        # Add/sub ints, longs, floats should be illegal
        for i in 1, 1L, 1.0:
            raises(TypeError, lambda: a+i)
            raises(TypeError, lambda: a-i)
            raises(TypeError, lambda: i+a)
            raises(TypeError, lambda: i-a)

        # delta - date is senseless.
        raises(TypeError, lambda: day - a)
        # mixing date and (delta or date) via * or // is senseless
        raises(TypeError, lambda: day * a)
        raises(TypeError, lambda: a * day)
        raises(TypeError, lambda: day // a)
        raises(TypeError, lambda: a // day)
        raises(TypeError, lambda: a * a)
        raises(TypeError, lambda: a // a)
        # date + date is senseless
        raises(TypeError, lambda: a + a)

    def test_overflow(self):
        tiny = self.theclass.resolution

        dt = self.theclass.min + tiny
        dt -= tiny  # no problem
        raises(OverflowError, dt.__sub__, tiny)
        raises(OverflowError, dt.__add__, -tiny)

        dt = self.theclass.max - tiny
        dt += tiny  # no problem
        raises(OverflowError, dt.__add__, tiny)
        raises(OverflowError, dt.__sub__, -tiny)

    def test_fromtimestamp(self):
        import time

        # Try an arbitrary fixed value.
        year, month, day = 1999, 9, 19
        ts = time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))
        d = self.theclass.fromtimestamp(ts)
        assert d.year == year
        assert d.month == month
        assert d.day == day

    def test_today(self):
        import time

        # We claim that today() is like fromtimestamp(time.time()), so
        # prove it.
        for dummy in range(3):
            today = self.theclass.today()
            ts = time.time()
            todayagain = self.theclass.fromtimestamp(ts)
            if today == todayagain:
                break
            # There are several legit reasons that could fail:
            # 1. It recently became midnight, between the today() and the
            #    time() calls.
            # 2. The platform time() has such fine resolution that we'll
            #    never get the same value twice.
            # 3. The platform time() has poor resolution, and we just
            #    happened to call today() right before a resolution quantum
            #    boundary.
            # 4. The system clock got fiddled between calls.
            # In any case, wait a little while and try again.
            time.sleep(0.1)

        # It worked or it didn't.  If it didn't, assume it's reason #2, and
        # let the test pass if they're within half a second of each other.
        assert (today == todayagain or
                        abs(todayagain - today) < timedelta(seconds=0.5))

    def test_weekday(self):
        for i in range(7):
            # March 4, 2002 is a Monday
            assert self.theclass(2002, 3, 4+i).weekday() == i
            assert self.theclass(2002, 3, 4+i).isoweekday() == i+1
            # January 2, 1956 is a Monday
            assert self.theclass(1956, 1, 2+i).weekday() == i
            assert self.theclass(1956, 1, 2+i).isoweekday() == i+1

    def test_isocalendar(self):
        # Check examples from
        # http://www.phys.uu.nl/~vgent/calendar/isocalendar.htm
        for i in range(7):
            d = self.theclass(2003, 12, 22+i)
            assert d.isocalendar() == (2003, 52, i+1)
            d = self.theclass(2003, 12, 29) + timedelta(i)
            assert d.isocalendar() == (2004, 1, i+1)
            d = self.theclass(2004, 1, 5+i)
            assert d.isocalendar() == (2004, 2, i+1)
            d = self.theclass(2009, 12, 21+i)
            assert d.isocalendar() == (2009, 52, i+1)
            d = self.theclass(2009, 12, 28) + timedelta(i)
            assert d.isocalendar() == (2009, 53, i+1)
            d = self.theclass(2010, 1, 4+i)
            assert d.isocalendar() == (2010, 1, i+1)

    def test_iso_long_years(self):
        # Calculate long ISO years and compare to table from
        # http://www.phys.uu.nl/~vgent/calendar/isocalendar.htm
        ISO_LONG_YEARS_TABLE = """
              4   32   60   88
              9   37   65   93
             15   43   71   99
             20   48   76
             26   54   82

            105  133  161  189
            111  139  167  195
            116  144  172
            122  150  178
            128  156  184

            201  229  257  285
            207  235  263  291
            212  240  268  296
            218  246  274
            224  252  280

            303  331  359  387
            308  336  364  392
            314  342  370  398
            320  348  376
            325  353  381
        """
        iso_long_years = map(int, ISO_LONG_YEARS_TABLE.split())
        iso_long_years.sort()
        L = []
        for i in range(400):
            d = self.theclass(2000+i, 12, 31)
            d1 = self.theclass(1600+i, 12, 31)
            assert d.isocalendar()[1:] == d1.isocalendar()[1:]
            if d.isocalendar()[1] == 53:
                L.append(i)
        assert L == iso_long_years

    def test_isoformat(self):
        t = self.theclass(2, 3, 2)
        assert t.isoformat() == "0002-03-02"

    def test_ctime(self):
        t = self.theclass(2002, 3, 2)
        assert t.ctime() == "Sat Mar  2 00:00:00 2002"

    def test_strftime(self):
        t = self.theclass(2005, 3, 2)
        assert t.strftime("m:%m d:%d y:%y") == "m:03 d:02 y:05"

        raises(TypeError, t.strftime) # needs an arg
        raises(TypeError, t.strftime, "one", "two") # too many args
        raises(TypeError, t.strftime, 42) # arg wrong type

        # A naive object replaces %z and %Z w/ empty strings.
        assert t.strftime("'%z' '%Z'") == "'' ''"

    def test_resolution_info(self):
        assert isinstance(self.theclass.min, self.theclass)
        assert isinstance(self.theclass.max, self.theclass)
        assert isinstance(self.theclass.resolution, timedelta)
        assert self.theclass.max > self.theclass.min

    def test_extreme_timedelta(self):
        big = self.theclass.max - self.theclass.min
        # 3652058 days, 23 hours, 59 minutes, 59 seconds, 999999 microseconds
        n = (big.days*24*3600 + big.seconds)*1000000 + big.microseconds
        # n == 315537897599999999 ~= 2**58.13
        justasbig = timedelta(0, 0, n)
        assert big == justasbig
        assert self.theclass.min + big == self.theclass.max
        assert self.theclass.max - big == self.theclass.min

    def test_timetuple(self):
        for i in range(7):
            # January 2, 1956 is a Monday (0)
            d = self.theclass(1956, 1, 2+i)
            t = d.timetuple()
            assert t == (1956, 1, 2+i, 0, 0, 0, i, 2+i, -1)
            # February 1, 1956 is a Wednesday (2)
            d = self.theclass(1956, 2, 1+i)
            t = d.timetuple()
            assert t == (1956, 2, 1+i, 0, 0, 0, (2+i)%7, 32+i, -1)
            # March 1, 1956 is a Thursday (3), and is the 31+29+1 = 61st day
            # of the year.
            d = self.theclass(1956, 3, 1+i)
            t = d.timetuple()
            assert t == (1956, 3, 1+i, 0, 0, 0, (3+i)%7, 61+i, -1)
            assert t.tm_year == 1956
            assert t.tm_mon == 3
            assert t.tm_mday == 1+i
            assert t.tm_hour == 0
            assert t.tm_min == 0
            assert t.tm_sec == 0
            assert t.tm_wday == (3+i)%7
            assert t.tm_yday == 61+i
            assert t.tm_isdst == -1

    def test_pickling(self):
        args = 6, 7, 23
        orig = self.theclass(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

    def test_compare(self):
        t1 = self.theclass(2, 3, 4)
        t2 = self.theclass(2, 3, 4)
        assert t1 == t2
        assert t1 <= t2
        assert t1 >= t2
        assert not t1 != t2
        assert not t1 < t2
        assert not t1 > t2
        assert cmp(t1, t2) == 0
        assert cmp(t2, t1) == 0

        for args in (3, 3, 3), (2, 4, 4), (2, 3, 5):
            t2 = self.theclass(*args)   # this is larger than t1
            assert t1 < t2
            assert t2 > t1
            assert t1 <= t2
            assert t2 >= t1
            assert t1 != t2
            assert t2 != t1
            assert not t1 == t2
            assert not t2 == t1
            assert not t1 > t2
            assert not t2 < t1
            assert not t1 >= t2
            assert not t2 <= t1
            assert cmp(t1, t2) == -1
            assert cmp(t2, t1) == 1

        for badarg in OTHERSTUFF:
            assert (t1 == badarg) == False
            assert (t1 != badarg) == True
            assert (badarg == t1) == False
            assert (badarg != t1) == True

            raises(TypeError, lambda: t1 < badarg)
            raises(TypeError, lambda: t1 > badarg)
            raises(TypeError, lambda: t1 >= badarg)
            raises(TypeError, lambda: badarg <= t1)
            raises(TypeError, lambda: badarg < t1)
            raises(TypeError, lambda: badarg > t1)
            raises(TypeError, lambda: badarg >= t1)

    def test_mixed_compare(self):
        our = self.theclass(2000, 4, 5)
        raises(TypeError, cmp, our, 1)
        raises(TypeError, cmp, 1, our)

        class AnotherDateTimeClass(object):
            def __cmp__(self, other):
                # Return "equal" so calling this can't be confused with
                # compare-by-address (which never says "equal" for distinct
                # objects).
                return 0

        # This still errors, because date and datetime comparison raise
        # TypeError instead of NotImplemented when they don't know what to
        # do, in order to stop comparison from falling back to the default
        # compare-by-address.
        their = AnotherDateTimeClass()
        raises(TypeError, cmp, our, their)
        # Oops:  The next stab raises TypeError in the C implementation,
        # but not in the Python implementation of datetime.  The difference
        # is due to that the Python implementation defines __cmp__ but
        # the C implementation defines tp_richcompare.  This is more pain
        # to fix than it's worth, so commenting out the test.
        # self.assertEqual(cmp(their, our), 0)

        # But date and datetime comparison return NotImplemented instead if the
        # other object has a timetuple attr.  This gives the other object a
        # chance to do the comparison.
        class Comparable(AnotherDateTimeClass):
            def timetuple(self):
                return ()

        their = Comparable()
        assert cmp(our, their) == 0
        assert cmp(their, our) == 0
        assert our == their
        assert their == our

    def test_bool(self):
        # All dates are considered true.
        assert self.theclass.min
        assert self.theclass.max

    def test_srftime_out_of_range(self):
        # For nasty technical reasons, we can't handle years before 1900.
        cls = self.theclass
        assert cls(1900, 1, 1).strftime("%Y") == "1900"
        for y in 1, 49, 51, 99, 100, 1000, 1899:
            raises(ValueError, cls(y, 1, 1).strftime, "%Y")

    def test_replace(self):
        cls = self.theclass
        args = [1, 2, 3]
        base = cls(*args)
        assert base == base.replace()

        i = 0
        for name, newval in (("year", 2),
                             ("month", 3),
                             ("day", 4)):
            newargs = args[:]
            newargs[i] = newval
            expected = cls(*newargs)
            got = base.replace(**{name: newval})
            assert expected == got
            i += 1

        # Out of bounds.
        base = cls(2000, 2, 29)
        raises(ValueError, base.replace, year=2001)

#############################################################################
# datetime tests

class TestDateTime(TestDate):

    theclass = datetime

    def test_basic_attributes(self):
        dt = self.theclass(2002, 3, 1, 12, 0)
        assert dt.year == 2002
        assert dt.month == 3
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.microsecond == 0

    def test_basic_attributes_nonzero(self):
        # Make sure all attributes are non-zero so bugs in
        # bit-shifting access show up.
        dt = self.theclass(2002, 3, 1, 12, 59, 59, 8000)
        assert dt.year == 2002
        assert dt.month == 3
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 59
        assert dt.second == 59
        assert dt.microsecond == 8000

    def test_roundtrip(self):
        for dt in (self.theclass(1, 2, 3, 4, 5, 6, 7),
                   self.theclass.now()):
            # Verify dt -> string -> datetime identity.
            s = repr(dt)
            assert s.startswith('datetime.')
            s = s[9:]
            dt2 = eval(s)
            assert dt == dt2

            # Verify identity via reconstructing from pieces.
            dt2 = self.theclass(dt.year, dt.month, dt.day,
                                dt.hour, dt.minute, dt.second,
                                dt.microsecond)
            assert dt == dt2

    def test_isoformat(self):
        t = self.theclass(2, 3, 2, 4, 5, 1, 123)
        assert t.isoformat() ==    "0002-03-02T04:05:01.000123"
        assert t.isoformat('T') == "0002-03-02T04:05:01.000123"
        assert t.isoformat(' ') == "0002-03-02 04:05:01.000123"
        # str is ISO format with the separator forced to a blank.
        assert str(t) == "0002-03-02 04:05:01.000123"

        t = self.theclass(2, 3, 2)
        assert t.isoformat() ==    "0002-03-02T00:00:00"
        assert t.isoformat('T') == "0002-03-02T00:00:00"
        assert t.isoformat(' ') == "0002-03-02 00:00:00"
        # str is ISO format with the separator forced to a blank.
        assert str(t) == "0002-03-02 00:00:00"

    def test_more_ctime(self):
        # Test fields that TestDate doesn't touch.
        import time

        t = self.theclass(2002, 3, 2, 18, 3, 5, 123)
        assert t.ctime() == "Sat Mar  2 18:03:05 2002"
        # Oops!  The next line fails on Win2K under MSVC 6, so it's commented
        # out.  The difference is that t.ctime() produces " 2" for the day,
        # but platform ctime() produces "02" for the day.  According to
        # C99, t.ctime() is correct here.
        # self.assertEqual(t.ctime(), time.ctime(time.mktime(t.timetuple())))

        # So test a case where that difference doesn't matter.
        t = self.theclass(2002, 3, 22, 18, 3, 5, 123)
        assert t.ctime() == time.ctime(time.mktime(t.timetuple()))

    def test_tz_independent_comparing(self):
        dt1 = self.theclass(2002, 3, 1, 9, 0, 0)
        dt2 = self.theclass(2002, 3, 1, 10, 0, 0)
        dt3 = self.theclass(2002, 3, 1, 9, 0, 0)
        assert dt1 == dt3
        assert dt2 > dt3

        # Make sure comparison doesn't forget microseconds, and isn't done
        # via comparing a float timestamp (an IEEE double doesn't have enough
        # precision to span microsecond resolution across years 1 thru 9999,
        # so comparing via timestamp necessarily calls some distinct values
        # equal).
        dt1 = self.theclass(MAXYEAR, 12, 31, 23, 59, 59, 999998)
        us = timedelta(microseconds=1)
        dt2 = dt1 + us
        assert dt2 - dt1 == us
        assert dt1 < dt2

    def test_bad_constructor_arguments(self):
        # bad years
        self.theclass(MINYEAR, 1, 1)  # no exception
        self.theclass(MAXYEAR, 1, 1)  # no exception
        raises(ValueError, self.theclass, MINYEAR-1, 1, 1)
        raises(ValueError, self.theclass, MAXYEAR+1, 1, 1)
        # bad months
        self.theclass(2000, 1, 1)    # no exception
        self.theclass(2000, 12, 1)   # no exception
        raises(ValueError, self.theclass, 2000, 0, 1)
        raises(ValueError, self.theclass, 2000, 13, 1)
        # bad days
        self.theclass(2000, 2, 29)   # no exception
        self.theclass(2004, 2, 29)   # no exception
        self.theclass(2400, 2, 29)   # no exception
        raises(ValueError, self.theclass, 2000, 2, 30)
        raises(ValueError, self.theclass, 2001, 2, 29)
        raises(ValueError, self.theclass, 2100, 2, 29)
        raises(ValueError, self.theclass, 1900, 2, 29)
        raises(ValueError, self.theclass, 2000, 1, 0)
        raises(ValueError, self.theclass, 2000, 1, 32)
        # bad hours
        self.theclass(2000, 1, 31, 0)    # no exception
        self.theclass(2000, 1, 31, 23)   # no exception
        raises(ValueError, self.theclass, 2000, 1, 31, -1)
        raises(ValueError, self.theclass, 2000, 1, 31, 24)
        # bad minutes
        self.theclass(2000, 1, 31, 23, 0)    # no exception
        self.theclass(2000, 1, 31, 23, 59)   # no exception
        raises(ValueError, self.theclass, 2000, 1, 31, 23, -1)
        raises(ValueError, self.theclass, 2000, 1, 31, 23, 60)
        # bad seconds
        self.theclass(2000, 1, 31, 23, 59, 0)    # no exception
        self.theclass(2000, 1, 31, 23, 59, 59)   # no exception
        raises(ValueError, self.theclass, 2000, 1, 31, 23, 59, -1)
        raises(ValueError, self.theclass, 2000, 1, 31, 23, 59, 60)
        # bad microseconds
        self.theclass(2000, 1, 31, 23, 59, 59, 0)    # no exception
        self.theclass(2000, 1, 31, 23, 59, 59, 999999)   # no exception
        raises(ValueError, self.theclass,
                          2000, 1, 31, 23, 59, 59, -1)
        raises(ValueError, self.theclass,
                          2000, 1, 31, 23, 59, 59,
                          1000000)

    def test_hash_equality(self):
        d = self.theclass(2000, 12, 31, 23, 30, 17)
        e = self.theclass(2000, 12, 31, 23, 30, 17)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

        d = self.theclass(2001,  1,  1,  0,  5, 17)
        e = self.theclass(2001,  1,  1,  0,  5, 17)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

    def test_computations(self):
        a = self.theclass(2002, 1, 31)
        b = self.theclass(1956, 1, 31)
        diff = a-b
        assert diff.days == 46*365 + len(range(1956, 2002, 4))
        assert diff.seconds == 0
        assert diff.microseconds == 0
        a = self.theclass(2002, 3, 2, 17, 6)
        millisec = timedelta(0, 0, 1000)
        hour = timedelta(0, 3600)
        day = timedelta(1)
        week = timedelta(7)
        assert a + hour == self.theclass(2002, 3, 2, 18, 6)
        assert hour + a == self.theclass(2002, 3, 2, 18, 6)
        assert a + 10*hour == self.theclass(2002, 3, 3, 3, 6)
        assert a - hour == self.theclass(2002, 3, 2, 16, 6)
        assert -hour + a == self.theclass(2002, 3, 2, 16, 6)
        assert a - hour == a + -hour
        assert a - 20*hour == self.theclass(2002, 3, 1, 21, 6)
        assert a + day == self.theclass(2002, 3, 3, 17, 6)
        assert a - day == self.theclass(2002, 3, 1, 17, 6)
        assert a + week == self.theclass(2002, 3, 9, 17, 6)
        assert a - week == self.theclass(2002, 2, 23, 17, 6)
        assert a + 52*week == self.theclass(2003, 3, 1, 17, 6)
        assert a - 52*week == self.theclass(2001, 3, 3, 17, 6)
        assert (a + week) - a == week
        assert (a + day) - a == day
        assert (a + hour) - a == hour
        assert (a + millisec) - a == millisec
        assert (a - week) - a == -week
        assert (a - day) - a == -day
        assert (a - hour) - a == -hour
        assert (a - millisec) - a == -millisec
        assert a - (a + week) == -week
        assert a - (a + day) == -day
        assert a - (a + hour) == -hour
        assert a - (a + millisec) == -millisec
        assert a - (a - week) == week
        assert a - (a - day) == day
        assert a - (a - hour) == hour
        assert a - (a - millisec) == millisec
        assert a + (week + day + hour + millisec) == (
                         self.theclass(2002, 3, 10, 18, 6, 0, 1000))
        assert a + (week + day + hour + millisec) == (
                         (((a + week) + day) + hour) + millisec)
        assert a - (week + day + hour + millisec) == (
                         self.theclass(2002, 2, 22, 16, 5, 59, 999000))
        assert a - (week + day + hour + millisec) == (
                         (((a - week) - day) - hour) - millisec)
        # Add/sub ints, longs, floats should be illegal
        for i in 1, 1L, 1.0:
            raises(TypeError, lambda: a+i)
            raises(TypeError, lambda: a-i)
            raises(TypeError, lambda: i+a)
            raises(TypeError, lambda: i-a)

        # delta - datetime is senseless.
        raises(TypeError, lambda: day - a)
        # mixing datetime and (delta or datetime) via * or // is senseless
        raises(TypeError, lambda: day * a)
        raises(TypeError, lambda: a * day)
        raises(TypeError, lambda: day // a)
        raises(TypeError, lambda: a // day)
        raises(TypeError, lambda: a * a)
        raises(TypeError, lambda: a // a)
        # datetime + datetime is senseless
        raises(TypeError, lambda: a + a)

    def test_pickling(self):
        args = 6, 7, 23, 20, 59, 1, 64**2
        orig = self.theclass(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

    def test_more_pickling(self):
        a = self.theclass(2003, 2, 7, 16, 48, 37, 444116)
        s = pickle.dumps(a)
        b = pickle.loads(s)
        assert b.year == 2003
        assert b.month == 2
        assert b.day == 7

    def test_more_compare(self):
        # The test_compare() inherited from TestDate covers the error cases.
        # We just want to test lexicographic ordering on the members datetime
        # has that date lacks.
        args = [2000, 11, 29, 20, 58, 16, 999998]
        t1 = self.theclass(*args)
        t2 = self.theclass(*args)
        assert t1 == t2
        assert t1 <= t2
        assert t1 >= t2
        assert not t1 != t2
        assert not t1 < t2
        assert not t1 > t2
        assert cmp(t1, t2) == 0
        assert cmp(t2, t1) == 0

        for i in range(len(args)):
            newargs = args[:]
            newargs[i] = args[i] + 1
            t2 = self.theclass(*newargs)   # this is larger than t1
            assert t1 < t2
            assert t2 > t1
            assert t1 <= t2
            assert t2 >= t1
            assert t1 != t2
            assert t2 != t1
            assert not t1 == t2
            assert not t2 == t1
            assert not t1 > t2
            assert not t2 < t1
            assert not t1 >= t2
            assert not t2 <= t1
            assert cmp(t1, t2) == -1
            assert cmp(t2, t1) == 1


    # A helper for timestamp constructor tests.
    def verify_field_equality(self, expected, got):
        assert expected.tm_year == got.year
        assert expected.tm_mon == got.month
        assert expected.tm_mday == got.day
        assert expected.tm_hour == got.hour
        assert expected.tm_min == got.minute
        assert expected.tm_sec == got.second

    def test_fromtimestamp(self):
        import time

        ts = time.time()
        expected = time.localtime(ts)
        got = self.theclass.fromtimestamp(ts)
        self.verify_field_equality(expected, got)

    def test_utcfromtimestamp(self):
        import time

        ts = time.time()
        expected = time.gmtime(ts)
        got = self.theclass.utcfromtimestamp(ts)
        self.verify_field_equality(expected, got)

    def test_utcnow(self):
        import time

        # Call it a success if utcnow() and utcfromtimestamp() are within
        # a second of each other.
        tolerance = timedelta(seconds=1)
        for dummy in range(3):
            from_now = self.theclass.utcnow()
            from_timestamp = self.theclass.utcfromtimestamp(time.time())
            if abs(from_timestamp - from_now) <= tolerance:
                break
            # Else try again a few times.
        assert abs(from_timestamp - from_now) <= tolerance

    def test_more_timetuple(self):
        # This tests fields beyond those tested by the TestDate.test_timetuple.
        t = self.theclass(2004, 12, 31, 6, 22, 33)
        assert t.timetuple() == (2004, 12, 31, 6, 22, 33, 4, 366, -1)
        assert t.timetuple() == (
                         (t.year, t.month, t.day,
                          t.hour, t.minute, t.second,
                          t.weekday(),
                          t.toordinal() - date(t.year, 1, 1).toordinal() + 1,
                          -1))
        tt = t.timetuple()
        assert tt.tm_year == t.year
        assert tt.tm_mon == t.month
        assert tt.tm_mday == t.day
        assert tt.tm_hour == t.hour
        assert tt.tm_min == t.minute
        assert tt.tm_sec == t.second
        assert tt.tm_wday == t.weekday()
        assert tt.tm_yday == ( t.toordinal() -
                                     date(t.year, 1, 1).toordinal() + 1)
        assert tt.tm_isdst == -1

    def test_more_strftime(self):
        # This tests fields beyond those tested by the TestDate.test_strftime.
        t = self.theclass(2004, 12, 31, 6, 22, 33)
        assert t.strftime("%m %d %y %S %M %H %j") == (
                                    "12 31 04 33 22 06 366")

    def test_extract(self):
        dt = self.theclass(2002, 3, 4, 18, 45, 3, 1234)
        assert dt.date() == date(2002, 3, 4)
        assert dt.time() == time(18, 45, 3, 1234)

    def test_combine(self):
        d = date(2002, 3, 4)
        t = time(18, 45, 3, 1234)
        expected = self.theclass(2002, 3, 4, 18, 45, 3, 1234)
        combine = self.theclass.combine
        dt = combine(d, t)
        assert dt == expected

        dt = combine(time=t, date=d)
        assert dt == expected

        assert d == dt.date()
        assert t == dt.time()
        assert dt == combine(dt.date(), dt.time())

        raises(TypeError, combine) # need an arg
        raises(TypeError, combine, d) # need two args
        raises(TypeError, combine, t, d) # args reversed
        raises(TypeError, combine, d, t, 1) # too many args
        raises(TypeError, combine, "date", "time") # wrong types

    def test_replace(self):
        cls = self.theclass
        args = [1, 2, 3, 4, 5, 6, 7]
        base = cls(*args)
        assert base == base.replace()

        i = 0
        for name, newval in (("year", 2),
                             ("month", 3),
                             ("day", 4),
                             ("hour", 5),
                             ("minute", 6),
                             ("second", 7),
                             ("microsecond", 8)):
            newargs = args[:]
            newargs[i] = newval
            expected = cls(*newargs)
            got = base.replace(**{name: newval})
            assert expected == got
            i += 1

        # Out of bounds.
        base = cls(2000, 2, 29)
        raises(ValueError, base.replace, year=2001)

    def test_astimezone(self):
        # Pretty boring!  The TZ test is more interesting here.  astimezone()
        # simply can't be applied to a naive object.
        dt = self.theclass.now()
        f = FixedOffset(44, "")
        raises(TypeError, dt.astimezone) # not enough args
        raises(TypeError, dt.astimezone, f, f) # too many args
        raises(TypeError, dt.astimezone, dt) # arg wrong type
        raises(ValueError, dt.astimezone, f) # naive
        raises(ValueError, dt.astimezone, tz=f)  # naive

        class Bogus(tzinfo):
            def utcoffset(self, dt): return None
            def dst(self, dt): return timedelta(0)
        bog = Bogus()
        raises(ValueError, dt.astimezone, bog)   # naive

        class AlsoBogus(tzinfo):
            def utcoffset(self, dt): return timedelta(0)
            def dst(self, dt): return None
        alsobog = AlsoBogus()
        raises(ValueError, dt.astimezone, alsobog) # also naive

class TestTime(HarmlessMixedComparison):

    theclass = time

    def test_basic_attributes(self):
        t = self.theclass(12, 0)
        assert t.hour == 12
        assert t.minute == 0
        assert t.second == 0
        assert t.microsecond == 0

    def test_basic_attributes_nonzero(self):
        # Make sure all attributes are non-zero so bugs in
        # bit-shifting access show up.
        t = self.theclass(12, 59, 59, 8000)
        assert t.hour == 12
        assert t.minute == 59
        assert t.second == 59
        assert t.microsecond == 8000

    def test_roundtrip(self):
        t = self.theclass(1, 2, 3, 4)

        # Verify t -> string -> time identity.
        s = repr(t)
        assert s.startswith('datetime.')
        s = s[9:]
        t2 = eval(s)
        assert t == t2

        # Verify identity via reconstructing from pieces.
        t2 = self.theclass(t.hour, t.minute, t.second,
                           t.microsecond)
        assert t == t2

    def test_comparing(self):
        args = [1, 2, 3, 4]
        t1 = self.theclass(*args)
        t2 = self.theclass(*args)
        assert t1 == t2
        assert t1 <= t2
        assert t1 >= t2
        assert not t1 != t2
        assert not t1 < t2
        assert not t1 > t2
        assert cmp(t1, t2) == 0
        assert cmp(t2, t1) == 0

        for i in range(len(args)):
            newargs = args[:]
            newargs[i] = args[i] + 1
            t2 = self.theclass(*newargs)   # this is larger than t1
            assert t1 < t2
            assert t2 > t1
            assert t1 <= t2
            assert t2 >= t1
            assert t1 != t2
            assert t2 != t1
            assert not t1 == t2
            assert not t2 == t1
            assert not t1 > t2
            assert not t2 < t1
            assert not t1 >= t2
            assert not t2 <= t1
            assert cmp(t1, t2) == -1
            assert cmp(t2, t1) == 1

        for badarg in OTHERSTUFF:
            assert (t1 == badarg) == False
            assert (t1 != badarg) == True
            assert (badarg == t1) == False
            assert (badarg != t1) == True

            raises(TypeError, lambda: t1 <= badarg)
            raises(TypeError, lambda: t1 < badarg)
            raises(TypeError, lambda: t1 > badarg)
            raises(TypeError, lambda: t1 >= badarg)
            raises(TypeError, lambda: badarg <= t1)
            raises(TypeError, lambda: badarg < t1)
            raises(TypeError, lambda: badarg > t1)
            raises(TypeError, lambda: badarg >= t1)

    def test_bad_constructor_arguments(self):
        # bad hours
        self.theclass(0, 0)    # no exception
        self.theclass(23, 0)   # no exception
        raises(ValueError, self.theclass, -1, 0)
        raises(ValueError, self.theclass, 24, 0)
        # bad minutes
        self.theclass(23, 0)    # no exception
        self.theclass(23, 59)   # no exception
        raises(ValueError, self.theclass, 23, -1)
        raises(ValueError, self.theclass, 23, 60)
        # bad seconds
        self.theclass(23, 59, 0)    # no exception
        self.theclass(23, 59, 59)   # no exception
        raises(ValueError, self.theclass, 23, 59, -1)
        raises(ValueError, self.theclass, 23, 59, 60)
        # bad microseconds
        self.theclass(23, 59, 59, 0)        # no exception
        self.theclass(23, 59, 59, 999999)   # no exception
        raises(ValueError, self.theclass, 23, 59, 59, -1)
        raises(ValueError, self.theclass, 23, 59, 59, 1000000)

    def test_hash_equality(self):
        d = self.theclass(23, 30, 17)
        e = self.theclass(23, 30, 17)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

        d = self.theclass(0,  5, 17)
        e = self.theclass(0,  5, 17)
        assert d == e
        assert hash(d) == hash(e)

        dic = {d: 1}
        dic[e] = 2
        assert len(dic) == 1
        assert dic[d] == 2
        assert dic[e] == 2

    def test_isoformat(self):
        t = self.theclass(4, 5, 1, 123)
        assert t.isoformat() == "04:05:01.000123"
        assert t.isoformat() == str(t)

        t = self.theclass()
        assert t.isoformat() == "00:00:00"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=1)
        assert t.isoformat() == "00:00:00.000001"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=10)
        assert t.isoformat() == "00:00:00.000010"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=100)
        assert t.isoformat() == "00:00:00.000100"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=1000)
        assert t.isoformat() == "00:00:00.001000"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=10000)
        assert t.isoformat() == "00:00:00.010000"
        assert t.isoformat() == str(t)

        t = self.theclass(microsecond=100000)
        assert t.isoformat() == "00:00:00.100000"
        assert t.isoformat() == str(t)

    def test_strftime(self):
        t = self.theclass(1, 2, 3, 4)
        assert t.strftime('%H %M %S') == "01 02 03"
        # A naive object replaces %z and %Z with empty strings.
        assert t.strftime("'%z' '%Z'") == "'' ''"

    def test_str(self):
        assert str(self.theclass(1, 2, 3, 4)) == "01:02:03.000004"
        assert str(self.theclass(10, 2, 3, 4000)) == "10:02:03.004000"
        assert str(self.theclass(0, 2, 3, 400000)) == "00:02:03.400000"
        assert str(self.theclass(12, 2, 3, 0)) == "12:02:03"
        assert str(self.theclass(23, 15, 0, 0)) == "23:15:00"

    def test_repr(self):
        name = 'datetime.' + self.theclass.__name__
        assert repr(self.theclass(1, 2, 3, 4)) == (
                         "%s(1, 2, 3, 4)" % name)
        assert repr(self.theclass(10, 2, 3, 4000)) == (
                         "%s(10, 2, 3, 4000)" % name)
        assert repr(self.theclass(0, 2, 3, 400000)) == (
                         "%s(0, 2, 3, 400000)" % name)
        assert repr(self.theclass(12, 2, 3, 0)) == (
                         "%s(12, 2, 3)" % name)
        assert repr(self.theclass(23, 15, 0, 0)) == (
                         "%s(23, 15)" % name)

    def test_resolution_info(self):
        assert isinstance(self.theclass.min, self.theclass)
        assert isinstance(self.theclass.max, self.theclass)
        assert isinstance(self.theclass.resolution, timedelta)
        assert self.theclass.max > self.theclass.min

    def test_pickling(self):
        args = 20, 59, 16, 64**2
        orig = self.theclass(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

    def test_bool(self):
        cls = self.theclass
        assert cls(1)
        assert cls(0, 1)
        assert cls(0, 0, 1)
        assert cls(0, 0, 0, 1)
        assert not cls(0)
        assert not cls()

    def test_replace(self):
        cls = self.theclass
        args = [1, 2, 3, 4]
        base = cls(*args)
        assert base == base.replace()

        i = 0
        for name, newval in (("hour", 5),
                             ("minute", 6),
                             ("second", 7),
                             ("microsecond", 8)):
            newargs = args[:]
            newargs[i] = newval
            expected = cls(*newargs)
            got = base.replace(**{name: newval})
            assert expected == got
            i += 1

        # Out of bounds.
        base = cls(1)
        raises(ValueError, base.replace, hour=24)
        raises(ValueError, base.replace, minute=-1)
        raises(ValueError, base.replace, second=100)
        raises(ValueError, base.replace, microsecond=1000000)

# A mixin for classes with a tzinfo= argument.  Subclasses must define
# theclass as a class atribute, and theclass(1, 1, 1, tzinfo=whatever)
# must be legit (which is true for time and datetime).
class TZInfoBase(object):

    def test_argument_passing(self):
        cls = self.theclass
        # A datetime passes itself on, a time passes None.
        class introspective(tzinfo):
            def tzname(self, dt):    return dt and "real" or "none"
            def utcoffset(self, dt):
                return timedelta(minutes = dt and 42 or -42)
            dst = utcoffset

        obj = cls(1, 2, 3, tzinfo=introspective())

        expected = cls is time and "none" or "real"
        assert obj.tzname() == expected

        expected = timedelta(minutes=(cls is time and -42 or 42))
        assert obj.utcoffset() == expected
        assert obj.dst() == expected

    def test_bad_tzinfo_classes(self):
        cls = self.theclass
        raises(TypeError, cls, 1, 1, 1, tzinfo=12)

        class NiceTry(object):
            def __init__(self): pass
            def utcoffset(self, dt): pass
        raises(TypeError, cls, 1, 1, 1, tzinfo=NiceTry)

        class BetterTry(tzinfo):
            def __init__(self): pass
            def utcoffset(self, dt): pass
        b = BetterTry()
        t = cls(1, 1, 1, tzinfo=b)
        assert t.tzinfo is b

    def test_utc_offset_out_of_bounds(self):
        class Edgy(tzinfo):
            def __init__(self, offset):
                self.offset = timedelta(minutes=offset)
            def utcoffset(self, dt):
                return self.offset

        cls = self.theclass
        for offset, legit in ((-1440, False),
                              (-1439, True),
                              (1439, True),
                              (1440, False)):
            if cls is time:
                t = cls(1, 2, 3, tzinfo=Edgy(offset))
            elif cls is datetime:
                t = cls(6, 6, 6, 1, 2, 3, tzinfo=Edgy(offset))
            else:
                assert 0, "impossible"
            if legit:
                aofs = abs(offset)
                h, m = divmod(aofs, 60)
                tag = "%c%02d:%02d" % (offset < 0 and '-' or '+', h, m)
                if isinstance(t, datetime):
                    t = t.timetz()
                assert str(t) == "01:02:03" + tag
            else:
                raises(ValueError, str, t)

    def test_tzinfo_classes(self):
        cls = self.theclass
        class C1(tzinfo):
            def utcoffset(self, dt): return None
            def dst(self, dt): return None
            def tzname(self, dt): return None
        for t in (cls(1, 1, 1),
                  cls(1, 1, 1, tzinfo=None),
                  cls(1, 1, 1, tzinfo=C1())):
            assert t.utcoffset() is None
            assert t.dst() is None
            assert t.tzname() is None

        class C3(tzinfo):
            def utcoffset(self, dt): return timedelta(minutes=-1439)
            def dst(self, dt): return timedelta(minutes=1439)
            def tzname(self, dt): return "aname"
        t = cls(1, 1, 1, tzinfo=C3())
        assert t.utcoffset() == timedelta(minutes=-1439)
        assert t.dst() == timedelta(minutes=1439)
        assert t.tzname() == "aname"

        # Wrong types.
        class C4(tzinfo):
            def utcoffset(self, dt): return "aname"
            def dst(self, dt): return 7
            def tzname(self, dt): return 0
        t = cls(1, 1, 1, tzinfo=C4())
        raises(TypeError, t.utcoffset)
        raises(TypeError, t.dst)
        raises(TypeError, t.tzname)

        # Offset out of range.
        class C6(tzinfo):
            def utcoffset(self, dt): return timedelta(hours=-24)
            def dst(self, dt): return timedelta(hours=24)
        t = cls(1, 1, 1, tzinfo=C6())
        raises(ValueError, t.utcoffset)
        raises(ValueError, t.dst)

        # Not a whole number of minutes.
        class C7(tzinfo):
            def utcoffset(self, dt): return timedelta(seconds=61)
            def dst(self, dt): return timedelta(microseconds=-81)
        t = cls(1, 1, 1, tzinfo=C7())
        raises(ValueError, t.utcoffset)
        raises(ValueError, t.dst)

    def test_aware_compare(self):
        cls = self.theclass

        # Ensure that utcoffset() gets ignored if the comparands have
        # the same tzinfo member.
        class OperandDependentOffset(tzinfo):
            def utcoffset(self, t):
                if t.minute < 10:
                    # d0 and d1 equal after adjustment
                    return timedelta(minutes=t.minute)
                else:
                    # d2 off in the weeds
                    return timedelta(minutes=59)

        base = cls(8, 9, 10, tzinfo=OperandDependentOffset())
        d0 = base.replace(minute=3)
        d1 = base.replace(minute=9)
        d2 = base.replace(minute=11)
        for x in d0, d1, d2:
            for y in d0, d1, d2:
                got = cmp(x, y)
                expected = cmp(x.minute, y.minute)
                assert got == expected

        # However, if they're different members, uctoffset is not ignored.
        # Note that a time can't actually have an operand-depedent offset,
        # though (and time.utcoffset() passes None to tzinfo.utcoffset()),
        # so skip this test for time.
        if cls is not time:
            d0 = base.replace(minute=3, tzinfo=OperandDependentOffset())
            d1 = base.replace(minute=9, tzinfo=OperandDependentOffset())
            d2 = base.replace(minute=11, tzinfo=OperandDependentOffset())
            for x in d0, d1, d2:
                for y in d0, d1, d2:
                    got = cmp(x, y)
                    if (x is d0 or x is d1) and (y is d0 or y is d1):
                        expected = 0
                    elif x is y is d2:
                        expected = 0
                    elif x is d2:
                        expected = -1
                    else:
                        assert y is d2
                        expected = 1
                    assert got == expected


# Testing time objects with a non-None tzinfo.
class TestTimeTZ(TestTime, TZInfoBase):
    theclass = time

    def test_empty(self):
        t = self.theclass()
        assert t.hour == 0
        assert t.minute == 0
        assert t.second == 0
        assert t.microsecond == 0
        assert t.tzinfo is None

    def test_zones(self):
        est = FixedOffset(-300, "EST", 1)
        utc = FixedOffset(0, "UTC", -2)
        met = FixedOffset(60, "MET", 3)
        t1 = time( 7, 47, tzinfo=est)
        t2 = time(12, 47, tzinfo=utc)
        t3 = time(13, 47, tzinfo=met)
        t4 = time(microsecond=40)
        t5 = time(microsecond=40, tzinfo=utc)

        assert t1.tzinfo == est
        assert t2.tzinfo == utc
        assert t3.tzinfo == met
        assert t4.tzinfo is None
        assert t5.tzinfo == utc

        assert t1.utcoffset() == timedelta(minutes=-300)
        assert t2.utcoffset() == timedelta(minutes=0)
        assert t3.utcoffset() == timedelta(minutes=60)
        assert t4.utcoffset() is None
        raises(TypeError, t1.utcoffset, "no args")

        assert t1.tzname() == "EST"
        assert t2.tzname() == "UTC"
        assert t3.tzname() == "MET"
        assert t4.tzname() is None
        raises(TypeError, t1.tzname, "no args")

        assert t1.dst() == timedelta(minutes=1)
        assert t2.dst() == timedelta(minutes=-2)
        assert t3.dst() == timedelta(minutes=3)
        assert t4.dst() is None
        raises(TypeError, t1.dst, "no args")

        assert hash(t1) == hash(t2)
        assert hash(t1) == hash(t3)
        assert hash(t2) == hash(t3)

        assert t1 == t2
        assert t1 == t3
        assert t2 == t3
        raises(TypeError, lambda: t4 == t5) # mixed tz-aware & naive
        raises(TypeError, lambda: t4 < t5) # mixed tz-aware & naive
        raises(TypeError, lambda: t5 < t4) # mixed tz-aware & naive

        assert str(t1) == "07:47:00-05:00"
        assert str(t2) == "12:47:00+00:00"
        assert str(t3) == "13:47:00+01:00"
        assert str(t4) == "00:00:00.000040"
        assert str(t5) == "00:00:00.000040+00:00"

        assert t1.isoformat() == "07:47:00-05:00"
        assert t2.isoformat() == "12:47:00+00:00"
        assert t3.isoformat() == "13:47:00+01:00"
        assert t4.isoformat() == "00:00:00.000040"
        assert t5.isoformat() == "00:00:00.000040+00:00"

        d = 'datetime.time'
        assert repr(t1) == d + "(7, 47, tzinfo=est)"
        assert repr(t2) == d + "(12, 47, tzinfo=utc)"
        assert repr(t3) == d + "(13, 47, tzinfo=met)"
        assert repr(t4) == d + "(0, 0, 0, 40)"
        assert repr(t5) == d + "(0, 0, 0, 40, tzinfo=utc)"

        assert t1.strftime("%H:%M:%S %%Z=%Z %%z=%z") == (
                                     "07:47:00 %Z=EST %z=-0500")
        assert t2.strftime("%H:%M:%S %Z %z") == "12:47:00 UTC +0000"
        assert t3.strftime("%H:%M:%S %Z %z") == "13:47:00 MET +0100"

        yuck = FixedOffset(-1439, "%z %Z %%z%%Z")
        t1 = time(23, 59, tzinfo=yuck)
        assert t1.strftime("%H:%M %%Z='%Z' %%z='%z'") == (
                                     "23:59 %Z='%z %Z %%z%%Z' %z='-2359'")

        # Check that an invalid tzname result raises an exception.
        class Badtzname(tzinfo):
            def tzname(self, dt): return 42
        t = time(2, 3, 4, tzinfo=Badtzname())
        assert t.strftime("%H:%M:%S") == "02:03:04"
        raises(TypeError, t.strftime, "%Z")

    def test_hash_edge_cases(self):
        # Offsets that overflow a basic time.
        t1 = self.theclass(0, 1, 2, 3, tzinfo=FixedOffset(1439, ""))
        t2 = self.theclass(0, 0, 2, 3, tzinfo=FixedOffset(1438, ""))
        assert hash(t1) == hash(t2)

        t1 = self.theclass(23, 58, 6, 100, tzinfo=FixedOffset(-1000, ""))
        t2 = self.theclass(23, 48, 6, 100, tzinfo=FixedOffset(-1010, ""))
        assert hash(t1) == hash(t2)

    def test_pickling(self):
        # Try one without a tzinfo.
        args = 20, 59, 16, 64**2
        orig = self.theclass(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

        # Try one with a tzinfo.
        tinfo = PicklableFixedOffset(-300, 'cookie')
        orig = self.theclass(5, 6, 7, tzinfo=tinfo)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived
            assert isinstance(derived.tzinfo, PicklableFixedOffset)
            assert derived.utcoffset() == timedelta(minutes=-300)
            assert derived.tzname() == 'cookie'

    def test_more_bool(self):
        # Test cases with non-None tzinfo.
        cls = self.theclass

        t = cls(0, tzinfo=FixedOffset(-300, ""))
        assert t

        t = cls(5, tzinfo=FixedOffset(-300, ""))
        assert t

        t = cls(5, tzinfo=FixedOffset(300, ""))
        assert not t

        t = cls(23, 59, tzinfo=FixedOffset(23*60 + 59, ""))
        assert not t

        # Mostly ensuring this doesn't overflow internally.
        t = cls(0, tzinfo=FixedOffset(23*60 + 59, ""))
        assert t

        # But this should yield a value error -- the utcoffset is bogus.
        t = cls(0, tzinfo=FixedOffset(24*60, ""))
        raises(ValueError, lambda: bool(t))

        # Likewise.
        t = cls(0, tzinfo=FixedOffset(-24*60, ""))
        raises(ValueError, lambda: bool(t))

    def test_replace(self):
        cls = self.theclass
        z100 = FixedOffset(100, "+100")
        zm200 = FixedOffset(timedelta(minutes=-200), "-200")
        args = [1, 2, 3, 4, z100]
        base = cls(*args)
        assert base == base.replace()

        i = 0
        for name, newval in (("hour", 5),
                             ("minute", 6),
                             ("second", 7),
                             ("microsecond", 8),
                             ("tzinfo", zm200)):
            newargs = args[:]
            newargs[i] = newval
            expected = cls(*newargs)
            got = base.replace(**{name: newval})
            assert expected == got
            i += 1

        # Ensure we can get rid of a tzinfo.
        assert base.tzname() == "+100"
        base2 = base.replace(tzinfo=None)
        assert base2.tzinfo is None
        assert base2.tzname() is None

        # Ensure we can add one.
        base3 = base2.replace(tzinfo=z100)
        assert base == base3
        assert base.tzinfo is base3.tzinfo

        # Out of bounds.
        base = cls(1)
        raises(ValueError, base.replace, hour=24)
        raises(ValueError, base.replace, minute=-1)
        raises(ValueError, base.replace, second=100)
        raises(ValueError, base.replace, microsecond=1000000)

    def test_mixed_compare(self):
        t1 = time(1, 2, 3)
        t2 = time(1, 2, 3)
        assert t1 == t2
        t2 = t2.replace(tzinfo=None)
        assert t1 == t2
        t2 = t2.replace(tzinfo=FixedOffset(None, ""))
        assert t1 == t2
        t2 = t2.replace(tzinfo=FixedOffset(0, ""))
        raises(TypeError, lambda: t1 == t2)

        # In time w/ identical tzinfo objects, utcoffset is ignored.
        class Varies(tzinfo):
            def __init__(self):
                self.offset = timedelta(minutes=22)
            def utcoffset(self, t):
                self.offset += timedelta(minutes=1)
                return self.offset

        v = Varies()
        t1 = t2.replace(tzinfo=v)
        t2 = t2.replace(tzinfo=v)
        assert t1.utcoffset() == timedelta(minutes=23)
        assert t2.utcoffset() == timedelta(minutes=24)
        assert t1 == t2

        # But if they're not identical, it isn't ignored.
        t2 = t2.replace(tzinfo=Varies())
        assert t1 < t2  # t1's offset counter still going up


# Testing datetime objects with a non-None tzinfo.

class TestDateTimeTZ(TestDateTime, TZInfoBase):
    theclass = datetime

    def test_trivial(self):
        dt = self.theclass(1, 2, 3, 4, 5, 6, 7)
        assert dt.year == 1
        assert dt.month == 2
        assert dt.day == 3
        assert dt.hour == 4
        assert dt.minute == 5
        assert dt.second == 6
        assert dt.microsecond == 7
        assert dt.tzinfo == None

    def test_even_more_compare(self):
        # The test_compare() and test_more_compare() inherited from TestDate
        # and TestDateTime covered non-tzinfo cases.

        # Smallest possible after UTC adjustment.
        t1 = self.theclass(1, 1, 1, tzinfo=FixedOffset(1439, ""))
        # Largest possible after UTC adjustment.
        t2 = self.theclass(MAXYEAR, 12, 31, 23, 59, 59, 999999,
                           tzinfo=FixedOffset(-1439, ""))

        # Make sure those compare correctly, and w/o overflow.
        assert t1 < t2
        assert t1 != t2
        assert t2 > t1

        assert t1 == t1
        assert t2 == t2

        # Equal afer adjustment.
        t1 = self.theclass(1, 12, 31, 23, 59, tzinfo=FixedOffset(1, ""))
        t2 = self.theclass(2, 1, 1, 3, 13, tzinfo=FixedOffset(3*60+13+2, ""))
        assert t1 == t2

        # Change t1 not to subtract a minute, and t1 should be larger.
        t1 = self.theclass(1, 12, 31, 23, 59, tzinfo=FixedOffset(0, ""))
        assert t1 > t2

        # Change t1 to subtract 2 minutes, and t1 should be smaller.
        t1 = self.theclass(1, 12, 31, 23, 59, tzinfo=FixedOffset(2, ""))
        assert t1 < t2

        # Back to the original t1, but make seconds resolve it.
        t1 = self.theclass(1, 12, 31, 23, 59, tzinfo=FixedOffset(1, ""),
                           second=1)
        assert t1 > t2

        # Likewise, but make microseconds resolve it.
        t1 = self.theclass(1, 12, 31, 23, 59, tzinfo=FixedOffset(1, ""),
                           microsecond=1)
        assert t1 > t2

        # Make t2 naive and it should fail.
        t2 = self.theclass.min
        raises(TypeError, lambda: t1 == t2)
        assert t2 == t2

        # It's also naive if it has tzinfo but tzinfo.utcoffset() is None.
        class Naive(tzinfo):
            def utcoffset(self, dt): return None
        t2 = self.theclass(5, 6, 7, tzinfo=Naive())
        raises(TypeError, lambda: t1 == t2)
        assert t2 == t2

        # OTOH, it's OK to compare two of these mixing the two ways of being
        # naive.
        t1 = self.theclass(5, 6, 7)
        assert t1 == t2

        # Try a bogus uctoffset.
        class Bogus(tzinfo):
            def utcoffset(self, dt):
                return timedelta(minutes=1440) # out of bounds
        t1 = self.theclass(2, 2, 2, tzinfo=Bogus())
        t2 = self.theclass(2, 2, 2, tzinfo=FixedOffset(0, ""))
        raises(ValueError, lambda: t1 == t2)

    def test_pickling(self):
        # Try one without a tzinfo.
        args = 6, 7, 23, 20, 59, 1, 64**2
        orig = self.theclass(*args)
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived

        # Try one with a tzinfo.
        tinfo = PicklableFixedOffset(-300, 'cookie')
        orig = self.theclass(*args, **{'tzinfo': tinfo})
        derived = self.theclass(1, 1, 1, tzinfo=FixedOffset(0, "", 0))
        for pickler, unpickler, proto in pickle_choices:
            green = pickler.dumps(orig, proto)
            derived = unpickler.loads(green)
            assert orig == derived
            assert isinstance(derived.tzinfo,
                            PicklableFixedOffset)
            assert derived.utcoffset() == timedelta(minutes=-300)
            assert derived.tzname() == 'cookie'

    def test_extreme_hashes(self):
        # If an attempt is made to hash these via subtracting the offset
        # then hashing a datetime object, OverflowError results.  The
        # Python implementation used to blow up here.
        t = self.theclass(1, 1, 1, tzinfo=FixedOffset(1439, ""))
        hash(t)
        t = self.theclass(MAXYEAR, 12, 31, 23, 59, 59, 999999,
                          tzinfo=FixedOffset(-1439, ""))
        hash(t)

        # OTOH, an OOB offset should blow up.
        t = self.theclass(5, 5, 5, tzinfo=FixedOffset(-1440, ""))
        raises(ValueError, hash, t)

    def test_zones(self):
        est = FixedOffset(-300, "EST")
        utc = FixedOffset(0, "UTC")
        met = FixedOffset(60, "MET")
        t1 = datetime(2002, 3, 19,  7, 47, tzinfo=est)
        t2 = datetime(2002, 3, 19, 12, 47, tzinfo=utc)
        t3 = datetime(2002, 3, 19, 13, 47, tzinfo=met)
        assert t1.tzinfo == est
        assert t2.tzinfo == utc
        assert t3.tzinfo == met
        assert t1.utcoffset() == timedelta(minutes=-300)
        assert t2.utcoffset() == timedelta(minutes=0)
        assert t3.utcoffset() == timedelta(minutes=60)
        assert t1.tzname() == "EST"
        assert t2.tzname() == "UTC"
        assert t3.tzname() == "MET"
        assert hash(t1) == hash(t2)
        assert hash(t1) == hash(t3)
        assert hash(t2) == hash(t3)
        assert t1 == t2
        assert t1 == t3
        assert t2 == t3
        assert str(t1) == "2002-03-19 07:47:00-05:00"
        assert str(t2) == "2002-03-19 12:47:00+00:00"
        assert str(t3) == "2002-03-19 13:47:00+01:00"
        d = 'datetime.datetime(2002, 3, 19, '
        assert repr(t1) == d + "7, 47, tzinfo=est)"
        assert repr(t2) == d + "12, 47, tzinfo=utc)"
        assert repr(t3) == d + "13, 47, tzinfo=met)"

    def test_combine(self):
        met = FixedOffset(60, "MET")
        d = date(2002, 3, 4)
        tz = time(18, 45, 3, 1234, tzinfo=met)
        dt = datetime.combine(d, tz)
        assert dt == datetime(2002, 3, 4, 18, 45, 3, 1234,
                                        tzinfo=met)

    def test_extract(self):
        met = FixedOffset(60, "MET")
        dt = self.theclass(2002, 3, 4, 18, 45, 3, 1234, tzinfo=met)
        assert dt.date() == date(2002, 3, 4)
        assert dt.time() == time(18, 45, 3, 1234)
        assert dt.timetz() == time(18, 45, 3, 1234, tzinfo=met)

    def test_tz_aware_arithmetic(self):
        import random

        now = self.theclass.now()
        tz55 = FixedOffset(-330, "west 5:30")
        timeaware = now.time().replace(tzinfo=tz55)
        nowaware = self.theclass.combine(now.date(), timeaware)
        assert nowaware.tzinfo is tz55
        assert nowaware.timetz() == timeaware

        # Can't mix aware and non-aware.
        raises(TypeError, lambda: now - nowaware)
        raises(TypeError, lambda: nowaware - now)

        # And adding datetime's doesn't make sense, aware or not.
        raises(TypeError, lambda: now + nowaware)
        raises(TypeError, lambda: nowaware + now)
        raises(TypeError, lambda: nowaware + nowaware)

        # Subtracting should yield 0.
        assert now - now == timedelta(0)
        assert nowaware - nowaware == timedelta(0)

        # Adding a delta should preserve tzinfo.
        delta = timedelta(weeks=1, minutes=12, microseconds=5678)
        nowawareplus = nowaware + delta
        assert nowaware.tzinfo is tz55
        nowawareplus2 = delta + nowaware
        assert nowawareplus2.tzinfo is tz55
        assert nowawareplus == nowawareplus2

        # that - delta should be what we started with, and that - what we
        # started with should be delta.
        diff = nowawareplus - delta
        assert diff.tzinfo is tz55
        assert nowaware == diff
        raises(TypeError, lambda: delta - nowawareplus)
        assert nowawareplus - nowaware == delta

        # Make up a random timezone.
        tzr = FixedOffset(random.randrange(-1439, 1440), "randomtimezone")
        # Attach it to nowawareplus.
        nowawareplus = nowawareplus.replace(tzinfo=tzr)
        assert nowawareplus.tzinfo is tzr
        # Make sure the difference takes the timezone adjustments into account.
        got = nowaware - nowawareplus
        # Expected:  (nowaware base - nowaware offset) -
        #            (nowawareplus base - nowawareplus offset) =
        #            (nowaware base - nowawareplus base) +
        #            (nowawareplus offset - nowaware offset) =
        #            -delta + nowawareplus offset - nowaware offset
        expected = nowawareplus.utcoffset() - nowaware.utcoffset() - delta
        assert got == expected

        # Try max possible difference.
        min = self.theclass(1, 1, 1, tzinfo=FixedOffset(1439, "min"))
        max = self.theclass(MAXYEAR, 12, 31, 23, 59, 59, 999999,
                            tzinfo=FixedOffset(-1439, "max"))
        maxdiff = max - min
        assert maxdiff == ( self.theclass.max - self.theclass.min +
                                  timedelta(minutes=2*1439))

    def test_tzinfo_now(self):
        meth = self.theclass.now
        # Ensure it doesn't require tzinfo (i.e., that this doesn't blow up).
        base = meth()
        # Try with and without naming the keyword.
        off42 = FixedOffset(42, "42")
        another = meth(off42)
        again = meth(tz=off42)
        assert another.tzinfo is again.tzinfo
        assert another.utcoffset() == timedelta(minutes=42)
        # Bad argument with and w/o naming the keyword.
        raises(TypeError, meth, 16)
        raises(TypeError, meth, tzinfo=16)
        # Bad keyword name.
        raises(TypeError, meth, tinfo=off42)
        # Too many args.
        raises(TypeError, meth, off42, off42)

        # We don't know which time zone we're in, and don't have a tzinfo
        # class to represent it, so seeing whether a tz argument actually
        # does a conversion is tricky.
        weirdtz = FixedOffset(timedelta(hours=15, minutes=58), "weirdtz", 0)
        utc = FixedOffset(0, "utc", 0)
        for dummy in range(3):
            now = datetime.now(weirdtz)
            assert now.tzinfo is weirdtz
            utcnow = datetime.utcnow().replace(tzinfo=utc)
            now2 = utcnow.astimezone(weirdtz)
            if abs(now - now2) < timedelta(seconds=30):
                break
            # Else the code is broken, or more than 30 seconds passed between
            # calls; assuming the latter, just try again.
        else:
            # Three strikes and we're out.
            raise AssertionError, "utcnow(), now(tz), or astimezone() may be broken"

    def test_tzinfo_fromtimestamp(self):
        import time
        meth = self.theclass.fromtimestamp
        ts = time.time()
        # Ensure it doesn't require tzinfo (i.e., that this doesn't blow up).
        base = meth(ts)
        # Try with and without naming the keyword.
        off42 = FixedOffset(42, "42")
        another = meth(ts, off42)
        again = meth(ts, tz=off42)
        assert another.tzinfo is again.tzinfo
        assert another.utcoffset() == timedelta(minutes=42)
        # Bad argument with and w/o naming the keyword.
        raises(TypeError, meth, ts, 16)
        raises(TypeError, meth, ts, tzinfo=16)
        # Bad keyword name.
        raises(TypeError, meth, ts, tinfo=off42)
        # Too many args.
        raises(TypeError, meth, ts, off42, off42)
        # Too few args.
        raises(TypeError, meth)

        # Try to make sure tz= actually does some conversion.
        timestamp = 1000000000
        utcdatetime = datetime.utcfromtimestamp(timestamp)
        # In POSIX (epoch 1970), that's 2001-09-09 01:46:40 UTC, give or take.
        # But on some flavor of Mac, it's nowhere near that.  So we can't have
        # any idea here what time that actually is, we can only test that
        # relative changes match.
        utcoffset = timedelta(hours=-15, minutes=39) # arbitrary, but not zero
        tz = FixedOffset(utcoffset, "tz", 0)
        expected = utcdatetime + utcoffset
        got = datetime.fromtimestamp(timestamp, tz)
        assert expected == got.replace(tzinfo=None)

    def test_tzinfo_utcnow(self):
        meth = self.theclass.utcnow
        # Ensure it doesn't require tzinfo (i.e., that this doesn't blow up).
        base = meth()
        # Try with and without naming the keyword; for whatever reason,
        # utcnow() doesn't accept a tzinfo argument.
        off42 = FixedOffset(42, "42")
        raises(TypeError, meth, off42)
        raises(TypeError, meth, tzinfo=off42)

    def test_tzinfo_utcfromtimestamp(self):
        import time
        meth = self.theclass.utcfromtimestamp
        ts = time.time()
        # Ensure it doesn't require tzinfo (i.e., that this doesn't blow up).
        base = meth(ts)
        # Try with and without naming the keyword; for whatever reason,
        # utcfromtimestamp() doesn't accept a tzinfo argument.
        off42 = FixedOffset(42, "42")
        raises(TypeError, meth, ts, off42)
        raises(TypeError, meth, ts, tzinfo=off42)

    def test_tzinfo_timetuple(self):
        # TestDateTime tested most of this.  datetime adds a twist to the
        # DST flag.
        class DST(tzinfo):
            def __init__(self, dstvalue):
                if isinstance(dstvalue, int):
                    dstvalue = timedelta(minutes=dstvalue)
                self.dstvalue = dstvalue
            def dst(self, dt):
                return self.dstvalue

        cls = self.theclass
        for dstvalue, flag in (-33, 1), (33, 1), (0, 0), (None, -1):
            d = cls(1, 1, 1, 10, 20, 30, 40, tzinfo=DST(dstvalue))
            t = d.timetuple()
            assert 1 == t.tm_year
            assert 1 == t.tm_mon
            assert 1 == t.tm_mday
            assert 10 == t.tm_hour
            assert 20 == t.tm_min
            assert 30 == t.tm_sec
            assert 0 == t.tm_wday
            assert 1 == t.tm_yday
            assert flag == t.tm_isdst

        # dst() returns wrong type.
        raises(TypeError, cls(1, 1, 1, tzinfo=DST("x")).timetuple)

        # dst() at the edge.
        assert cls(1,1,1, tzinfo=DST(1439)).timetuple().tm_isdst == 1
        assert cls(1,1,1, tzinfo=DST(-1439)).timetuple().tm_isdst == 1

        # dst() out of range.
        raises(ValueError, cls(1,1,1, tzinfo=DST(1440)).timetuple)
        raises(ValueError, cls(1,1,1, tzinfo=DST(-1440)).timetuple)

    def test_utctimetuple(self):
        class DST(tzinfo):
            def __init__(self, dstvalue):
                if isinstance(dstvalue, int):
                    dstvalue = timedelta(minutes=dstvalue)
                self.dstvalue = dstvalue
            def dst(self, dt):
                return self.dstvalue

        cls = self.theclass
        # This can't work:  DST didn't implement utcoffset.
        raises(NotImplementedError,
                          cls(1, 1, 1, tzinfo=DST(0)).utcoffset)

        class UOFS(DST):
            def __init__(self, uofs, dofs=None):
                DST.__init__(self, dofs)
                self.uofs = timedelta(minutes=uofs)
            def utcoffset(self, dt):
                return self.uofs

        # Ensure tm_isdst is 0 regardless of what dst() says:  DST is never
        # in effect for a UTC time.
        for dstvalue in -33, 33, 0, None:
            d = cls(1, 2, 3, 10, 20, 30, 40, tzinfo=UOFS(-53, dstvalue))
            t = d.utctimetuple()
            assert d.year == t.tm_year
            assert d.month == t.tm_mon
            assert d.day == t.tm_mday
            assert 11 == t.tm_hour # 20mm + 53mm = 1hn + 13mm
            assert 13 == t.tm_min
            assert d.second == t.tm_sec
            assert d.weekday() == t.tm_wday
            assert d.toordinal() - date(1, 1, 1).toordinal() + 1 == (
                             t.tm_yday)
            assert 0 == t.tm_isdst

        # At the edges, UTC adjustment can normalize into years out-of-range
        # for a datetime object.  Ensure that a correct timetuple is
        # created anyway.
        tiny = cls(MINYEAR, 1, 1, 0, 0, 37, tzinfo=UOFS(1439))
        # That goes back 1 minute less than a full day.
        t = tiny.utctimetuple()
        assert t.tm_year == MINYEAR-1
        assert t.tm_mon == 12
        assert t.tm_mday == 31
        assert t.tm_hour == 0
        assert t.tm_min == 1
        assert t.tm_sec == 37
        assert t.tm_yday == 366    # "year 0" is a leap year
        assert t.tm_isdst == 0

        huge = cls(MAXYEAR, 12, 31, 23, 59, 37, 999999, tzinfo=UOFS(-1439))
        # That goes forward 1 minute less than a full day.
        t = huge.utctimetuple()
        assert t.tm_year == MAXYEAR+1
        assert t.tm_mon == 1
        assert t.tm_mday == 1
        assert t.tm_hour == 23
        assert t.tm_min == 58
        assert t.tm_sec == 37
        assert t.tm_yday == 1
        assert t.tm_isdst == 0

    def test_tzinfo_isoformat(self):
        zero = FixedOffset(0, "+00:00")
        plus = FixedOffset(220, "+03:40")
        minus = FixedOffset(-231, "-03:51")
        unknown = FixedOffset(None, "")

        cls = self.theclass
        datestr = '0001-02-03'
        for ofs in None, zero, plus, minus, unknown:
            for us in 0, 987001:
                d = cls(1, 2, 3, 4, 5, 59, us, tzinfo=ofs)
                timestr = '04:05:59' + (us and '.987001' or '')
                ofsstr = ofs is not None and d.tzname() or ''
                tailstr = timestr + ofsstr
                iso = d.isoformat()
                assert iso == datestr + 'T' + tailstr
                assert iso == d.isoformat('T')
                assert d.isoformat('k') == datestr + 'k' + tailstr
                assert str(d) == datestr + ' ' + tailstr

    def test_replace(self):
        cls = self.theclass
        z100 = FixedOffset(100, "+100")
        zm200 = FixedOffset(timedelta(minutes=-200), "-200")
        args = [1, 2, 3, 4, 5, 6, 7, z100]
        base = cls(*args)
        assert base == base.replace()

        i = 0
        for name, newval in (("year", 2),
                             ("month", 3),
                             ("day", 4),
                             ("hour", 5),
                             ("minute", 6),
                             ("second", 7),
                             ("microsecond", 8),
                             ("tzinfo", zm200)):
            newargs = args[:]
            newargs[i] = newval
            expected = cls(*newargs)
            got = base.replace(**{name: newval})
            assert expected == got
            i += 1

        # Ensure we can get rid of a tzinfo.
        assert base.tzname() == "+100"
        base2 = base.replace(tzinfo=None)
        assert base2.tzinfo is None
        assert base2.tzname() is None

        # Ensure we can add one.
        base3 = base2.replace(tzinfo=z100)
        assert base == base3
        assert base.tzinfo is base3.tzinfo

        # Out of bounds.
        base = cls(2000, 2, 29)
        raises(ValueError, base.replace, year=2001)

    def test_more_astimezone(self):
        # The inherited test_astimezone covered some trivial and error cases.
        fnone = FixedOffset(None, "None")
        f44m = FixedOffset(44, "44")
        fm5h = FixedOffset(-timedelta(hours=5), "m300")

        dt = self.theclass.now(tz=f44m)
        assert dt.tzinfo is f44m
        # Replacing with degenerate tzinfo raises an exception.
        raises(ValueError, dt.astimezone, fnone)
        # Ditto with None tz.
        raises(TypeError, dt.astimezone, None)
        # Replacing with same tzinfo makes no change.
        x = dt.astimezone(dt.tzinfo)
        assert x.tzinfo is f44m
        assert x.date() == dt.date()
        assert x.time() == dt.time()

        # Replacing with different tzinfo does adjust.
        got = dt.astimezone(fm5h)
        assert got.tzinfo is fm5h
        assert got.utcoffset() == timedelta(hours=-5)
        expected = dt - dt.utcoffset()  # in effect, convert to UTC
        expected += fm5h.utcoffset(dt)  # and from there to local time
        expected = expected.replace(tzinfo=fm5h) # and attach new tzinfo
        assert got.date() == expected.date()
        assert got.time() == expected.time()
        assert got.timetz() == expected.timetz()
        assert got.tzinfo is expected.tzinfo
        assert got == expected

    def test_aware_subtract(self):
        cls = self.theclass

        # Ensure that utcoffset() is ignored when the operands have the
        # same tzinfo member.
        class OperandDependentOffset(tzinfo):
            def utcoffset(self, t):
                if t.minute < 10:
                    # d0 and d1 equal after adjustment
                    return timedelta(minutes=t.minute)
                else:
                    # d2 off in the weeds
                    return timedelta(minutes=59)

        base = cls(8, 9, 10, 11, 12, 13, 14, tzinfo=OperandDependentOffset())
        d0 = base.replace(minute=3)
        d1 = base.replace(minute=9)
        d2 = base.replace(minute=11)
        for x in d0, d1, d2:
            for y in d0, d1, d2:
                got = x - y
                expected = timedelta(minutes=x.minute - y.minute)
                assert got == expected

        # OTOH, if the tzinfo members are distinct, utcoffsets aren't
        # ignored.
        base = cls(8, 9, 10, 11, 12, 13, 14)
        d0 = base.replace(minute=3, tzinfo=OperandDependentOffset())
        d1 = base.replace(minute=9, tzinfo=OperandDependentOffset())
        d2 = base.replace(minute=11, tzinfo=OperandDependentOffset())
        for x in d0, d1, d2:
            for y in d0, d1, d2:
                got = x - y
                if (x is d0 or x is d1) and (y is d0 or y is d1):
                    expected = timedelta(0)
                elif x is y is d2:
                    expected = timedelta(0)
                elif x is d2:
                    expected = timedelta(minutes=(11-59)-0)
                else:
                    assert y is d2
                    expected = timedelta(minutes=0-(11-59))
                assert got == expected

    def test_mixed_compare(self):
        t1 = datetime(1, 2, 3, 4, 5, 6, 7)
        t2 = datetime(1, 2, 3, 4, 5, 6, 7)
        assert t1 == t2
        t2 = t2.replace(tzinfo=None)
        assert t1 == t2
        t2 = t2.replace(tzinfo=FixedOffset(None, ""))
        assert t1 == t2
        t2 = t2.replace(tzinfo=FixedOffset(0, ""))
        raises(TypeError, lambda: t1 == t2)

        # In datetime w/ identical tzinfo objects, utcoffset is ignored.
        class Varies(tzinfo):
            def __init__(self):
                self.offset = timedelta(minutes=22)
            def utcoffset(self, t):
                self.offset += timedelta(minutes=1)
                return self.offset

        v = Varies()
        t1 = t2.replace(tzinfo=v)
        t2 = t2.replace(tzinfo=v)
        assert t1.utcoffset() == timedelta(minutes=23)
        assert t2.utcoffset() == timedelta(minutes=24)
        assert t1 == t2

        # But if they're not identical, it isn't ignored.
        t2 = t2.replace(tzinfo=Varies())
        assert t1 < t2  # t1's offset counter still going up

# Pain to set up DST-aware tzinfo classes.

def first_sunday_on_or_after(dt):
    days_to_go = 6 - dt.weekday()
    if days_to_go:
        dt += timedelta(days_to_go)
    return dt

ZERO = timedelta(0)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
# In the US, DST starts at 2am (standard time) on the first Sunday in April.
DSTSTART = datetime(1, 4, 1, 2)
# and ends at 2am (DST time; 1am standard time) on the last Sunday of Oct,
# which is the first Sunday on or after Oct 25.  Because we view 1:MM as
# being standard time on that day, there is no spelling in local time of
# the last hour of DST (that's 1:MM DST, but 1:MM is taken as standard time).
DSTEND = datetime(1, 10, 25, 1)

class USTimeZone(tzinfo):

    def __init__(self, hours, reprname, stdname, dstname):
        self.stdoffset = timedelta(hours=hours)
        self.reprname = reprname
        self.stdname = stdname
        self.dstname = dstname

    def __repr__(self):
        return self.reprname

    def tzname(self, dt):
        if self.dst(dt):
            return self.dstname
        else:
            return self.stdname

    def utcoffset(self, dt):
        return self.stdoffset + self.dst(dt)

    def dst(self, dt):
        if dt is None or dt.tzinfo is None:
            # An exception instead may be sensible here, in one or more of
            # the cases.
            return ZERO
        assert dt.tzinfo is self

        # Find first Sunday in April.
        start = first_sunday_on_or_after(DSTSTART.replace(year=dt.year))
        assert start.weekday() == 6 and start.month == 4 and start.day <= 7

        # Find last Sunday in October.
        end = first_sunday_on_or_after(DSTEND.replace(year=dt.year))
        assert end.weekday() == 6 and end.month == 10 and end.day >= 25

        # Can't compare naive to aware objects, so strip the timezone from
        # dt first.
        if start <= dt.replace(tzinfo=None) < end:
            return HOUR
        else:
            return ZERO

Eastern  = USTimeZone(-5, "Eastern",  "EST", "EDT")
Central  = USTimeZone(-6, "Central",  "CST", "CDT")
Mountain = USTimeZone(-7, "Mountain", "MST", "MDT")
Pacific  = USTimeZone(-8, "Pacific",  "PST", "PDT")
utc_real = FixedOffset(0, "UTC", 0)
# For better test coverage, we want another flavor of UTC that's west of
# the Eastern and Pacific timezones.
utc_fake = FixedOffset(-12*60, "UTCfake", 0)

class TestTimezoneConversions(object):
    # The DST switch times for 2002, in std time.
    dston = datetime(2002, 4, 7, 2)
    dstoff = datetime(2002, 10, 27, 1)

    theclass = datetime

    # Check a time that's inside DST.
    def checkinside(self, dt, tz, utc, dston, dstoff):
        assert dt.dst() == HOUR

        # Conversion to our own timezone is always an identity.
        assert dt.astimezone(tz) == dt

        asutc = dt.astimezone(utc)
        there_and_back = asutc.astimezone(tz)

        # Conversion to UTC and back isn't always an identity here,
        # because there are redundant spellings (in local time) of
        # UTC time when DST begins:  the clock jumps from 1:59:59
        # to 3:00:00, and a local time of 2:MM:SS doesn't really
        # make sense then.  The classes above treat 2:MM:SS as
        # daylight time then (it's "after 2am"), really an alias
        # for 1:MM:SS standard time.  The latter form is what
        # conversion back from UTC produces.
        if dt.date() == dston.date() and dt.hour == 2:
            # We're in the redundant hour, and coming back from
            # UTC gives the 1:MM:SS standard-time spelling.
            assert there_and_back + HOUR == dt
            # Although during was considered to be in daylight
            # time, there_and_back is not.
            assert there_and_back.dst() == ZERO
            # They're the same times in UTC.
            assert there_and_back.astimezone(utc) == (
                             dt.astimezone(utc))
        else:
            # We're not in the redundant hour.
            assert dt == there_and_back

        # Because we have a redundant spelling when DST begins, there is
        # (unforunately) an hour when DST ends that can't be spelled at all in
        # local time.  When DST ends, the clock jumps from 1:59 back to 1:00
        # again.  The hour 1:MM DST has no spelling then:  1:MM is taken to be
        # standard time.  1:MM DST == 0:MM EST, but 0:MM is taken to be
        # daylight time.  The hour 1:MM daylight == 0:MM standard can't be
        # expressed in local time.  Nevertheless, we want conversion back
        # from UTC to mimic the local clock's "repeat an hour" behavior.
        nexthour_utc = asutc + HOUR
        nexthour_tz = nexthour_utc.astimezone(tz)
        if dt.date() == dstoff.date() and dt.hour == 0:
            # We're in the hour before the last DST hour.  The last DST hour
            # is ineffable.  We want the conversion back to repeat 1:MM.
            assert nexthour_tz == dt.replace(hour=1)
            nexthour_utc += HOUR
            nexthour_tz = nexthour_utc.astimezone(tz)
            assert nexthour_tz == dt.replace(hour=1)
        else:
            assert nexthour_tz - dt == HOUR

    # Check a time that's outside DST.
    def checkoutside(self, dt, tz, utc):
        assert dt.dst() == ZERO

        # Conversion to our own timezone is always an identity.
        assert dt.astimezone(tz) == dt

        # Converting to UTC and back is an identity too.
        asutc = dt.astimezone(utc)
        there_and_back = asutc.astimezone(tz)
        assert dt == there_and_back

    def convert_between_tz_and_utc(self, tz, utc):
        dston = self.dston.replace(tzinfo=tz)
        # Because 1:MM on the day DST ends is taken as being standard time,
        # there is no spelling in tz for the last hour of daylight time.
        # For purposes of the test, the last hour of DST is 0:MM, which is
        # taken as being daylight time (and 1:MM is taken as being standard
        # time).
        dstoff = self.dstoff.replace(tzinfo=tz)
        for delta in (timedelta(weeks=13),
                      DAY,
                      HOUR,
                      timedelta(minutes=1),
                      timedelta(microseconds=1)):

            self.checkinside(dston, tz, utc, dston, dstoff)
            for during in dston + delta, dstoff - delta:
                self.checkinside(during, tz, utc, dston, dstoff)

            self.checkoutside(dstoff, tz, utc)
            for outside in dston - delta, dstoff + delta:
                self.checkoutside(outside, tz, utc)

    def test_easy(self):
        # Despite the name of this test, the endcases are excruciating.
        self.convert_between_tz_and_utc(Eastern, utc_real)
        self.convert_between_tz_and_utc(Pacific, utc_real)
        self.convert_between_tz_and_utc(Eastern, utc_fake)
        self.convert_between_tz_and_utc(Pacific, utc_fake)
        # The next is really dancing near the edge.  It works because
        # Pacific and Eastern are far enough apart that their "problem
        # hours" don't overlap.
        self.convert_between_tz_and_utc(Eastern, Pacific)
        self.convert_between_tz_and_utc(Pacific, Eastern)
        # OTOH, these fail!  Don't enable them.  The difficulty is that
        # the edge case tests assume that every hour is representable in
        # the "utc" class.  This is always true for a fixed-offset tzinfo
        # class (lke utc_real and utc_fake), but not for Eastern or Central.
        # For these adjacent DST-aware time zones, the range of time offsets
        # tested ends up creating hours in the one that aren't representable
        # in the other.  For the same reason, we would see failures in the
        # Eastern vs Pacific tests too if we added 3*HOUR to the list of
        # offset deltas in convert_between_tz_and_utc().
        #
        # self.convert_between_tz_and_utc(Eastern, Central)  # can't work
        # self.convert_between_tz_and_utc(Central, Eastern)  # can't work

    def test_tricky(self):
        # 22:00 on day before daylight starts.
        fourback = self.dston - timedelta(hours=4)
        ninewest = FixedOffset(-9*60, "-0900", 0)
        fourback = fourback.replace(tzinfo=ninewest)
        # 22:00-0900 is 7:00 UTC == 2:00 EST == 3:00 DST.  Since it's "after
        # 2", we should get the 3 spelling.
        # If we plug 22:00 the day before into Eastern, it "looks like std
        # time", so its offset is returned as -5, and -5 - -9 = 4.  Adding 4
        # to 22:00 lands on 2:00, which makes no sense in local time (the
        # local clock jumps from 1 to 3).  The point here is to make sure we
        # get the 3 spelling.
        expected = self.dston.replace(hour=3)
        got = fourback.astimezone(Eastern).replace(tzinfo=None)
        assert expected == got

        # Similar, but map to 6:00 UTC == 1:00 EST == 2:00 DST.  In that
        # case we want the 1:00 spelling.
        sixutc = self.dston.replace(hour=6, tzinfo=utc_real)
        # Now 6:00 "looks like daylight", so the offset wrt Eastern is -4,
        # and adding -4-0 == -4 gives the 2:00 spelling.  We want the 1:00 EST
        # spelling.
        expected = self.dston.replace(hour=1)
        got = sixutc.astimezone(Eastern).replace(tzinfo=None)
        assert expected == got

        # Now on the day DST ends, we want "repeat an hour" behavior.
        #  UTC  4:MM  5:MM  6:MM  7:MM  checking these
        #  EST 23:MM  0:MM  1:MM  2:MM
        #  EDT  0:MM  1:MM  2:MM  3:MM
        # wall  0:MM  1:MM  1:MM  2:MM  against these
        for utc in utc_real, utc_fake:
            for tz in Eastern, Pacific:
                first_std_hour = self.dstoff - timedelta(hours=2) # 23:MM
                # Convert that to UTC.
                first_std_hour -= tz.utcoffset(None)
                # Adjust for possibly fake UTC.
                asutc = first_std_hour + utc.utcoffset(None)
                # First UTC hour to convert; this is 4:00 when utc=utc_real &
                # tz=Eastern.
                asutcbase = asutc.replace(tzinfo=utc)
                for tzhour in (0, 1, 1, 2):
                    expectedbase = self.dstoff.replace(hour=tzhour)
                    for minute in 0, 30, 59:
                        expected = expectedbase.replace(minute=minute)
                        asutc = asutcbase.replace(minute=minute)
                        astz = asutc.astimezone(tz)
                        assert astz.replace(tzinfo=None) == expected
                    asutcbase += HOUR


    def test_bogus_dst(self):
        class ok(tzinfo):
            def utcoffset(self, dt): return HOUR
            def dst(self, dt): return HOUR

        now = self.theclass.now().replace(tzinfo=utc_real)
        # Doesn't blow up.
        now.astimezone(ok())

        # Does blow up.
        class notok(ok):
            def dst(self, dt): return None
        raises(ValueError, now.astimezone, notok())

    def test_fromutc(self):
        raises(TypeError, Eastern.fromutc)   # not enough args
        now = datetime.utcnow().replace(tzinfo=utc_real)
        raises(ValueError, Eastern.fromutc, now) # wrong tzinfo
        now = now.replace(tzinfo=Eastern)   # insert correct tzinfo
        enow = Eastern.fromutc(now)         # doesn't blow up
        assert enow.tzinfo == Eastern # has right tzinfo member
        raises(TypeError, Eastern.fromutc, now, now) # too many args
        raises(TypeError, Eastern.fromutc, date.today()) # wrong type

        # Always converts UTC to standard time.
        class FauxUSTimeZone(USTimeZone):
            def fromutc(self, dt):
                return dt + self.stdoffset
        FEastern  = FauxUSTimeZone(-5, "FEastern",  "FEST", "FEDT")

        #  UTC  4:MM  5:MM  6:MM  7:MM  8:MM  9:MM
        #  EST 23:MM  0:MM  1:MM  2:MM  3:MM  4:MM
        #  EDT  0:MM  1:MM  2:MM  3:MM  4:MM  5:MM

        # Check around DST start.
        start = self.dston.replace(hour=4, tzinfo=Eastern)
        fstart = start.replace(tzinfo=FEastern)
        for wall in 23, 0, 1, 3, 4, 5:
            expected = start.replace(hour=wall)
            if wall == 23:
                expected -= timedelta(days=1)
            got = Eastern.fromutc(start)
            assert expected == got

            expected = fstart + FEastern.stdoffset
            got = FEastern.fromutc(fstart)
            assert expected == got

            # Ensure astimezone() calls fromutc() too.
            got = fstart.replace(tzinfo=utc_real).astimezone(FEastern)
            assert expected == got

            start += HOUR
            fstart += HOUR

        # Check around DST end.
        start = self.dstoff.replace(hour=4, tzinfo=Eastern)
        fstart = start.replace(tzinfo=FEastern)
        for wall in 0, 1, 1, 2, 3, 4:
            expected = start.replace(hour=wall)
            got = Eastern.fromutc(start)
            assert expected == got

            expected = fstart + FEastern.stdoffset
            got = FEastern.fromutc(fstart)
            assert expected == got

            # Ensure astimezone() calls fromutc() too.
            got = fstart.replace(tzinfo=utc_real).astimezone(FEastern)
            assert expected == got

            start += HOUR
            fstart += HOUR

