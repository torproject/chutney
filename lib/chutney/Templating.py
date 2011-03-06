#!/usr/bin/python
#
# Copyright 2011 Nick Mathewson, Michael Stone
#
#  You may do anything with this work that copyright law would normally
#  restrict, so long as you retain the above notice(s) and this license
#  in all redistributed copies and derived works.  There is no warranty.

"""
>>> base = Environ(foo=99, bar=600)
>>> derived1 = Environ(parent=base, bar=700, quux=32)
>>> base["foo"]
99
>>> sorted(base.keys())
['bar', 'foo']
>>> derived1["foo"]
99
>>> base["bar"]
600
>>> derived1["bar"]
700
>>> derived1["quux"]
32
>>> sorted(derived1.keys())
['bar', 'foo', 'quux']
>>> class Specialized(Environ):
...    def __init__(self, p=None, **kw):
...       Environ.__init__(self, p, **kw)
...       self._n_calls = 0
...    def _get_expensive_value(self, my):
...       self._n_calls += 1
...       return "Let's pretend this is hard to compute"
...
>>> s = Specialized(base, quux="hi")
>>> s["quux"]
'hi'
>>> s['expensive_value']
"Let's pretend this is hard to compute"
>>> s['expensive_value']
"Let's pretend this is hard to compute"
>>> s._n_calls
1
>>> sorted(s.keys())
['bar', 'expensive_value', 'foo', 'quux']

>>> bt = _BetterTemplate("Testing ${hello}, $goodbye$$, $foo , ${a:b:c}")
>>> bt.safe_substitute({'a:b:c': "4"}, hello=1, goodbye=2, foo=3)
'Testing 1, 2$, 3 , 4'

>>> t = Template("${include:/dev/null} $hi_there")
>>> sorted(t.freevars())
['hi_there']
>>> t.format(dict(hi_there=99))
' 99'
>>> t2 = Template("X$${include:$fname} $bar $baz")
>>> t2.format(dict(fname="/dev/null", bar=33, baz="$foo", foo=1337))
'X 33 1337'
>>> sorted(t2.freevars({'fname':"/dev/null"}))
['bar', 'baz', 'fname']

"""

from __future__ import with_statement

import string
import os

#class _KeyError(KeyError):
#    pass

_KeyError = KeyError

class _DictWrapper(object):
    def __init__(self, parent=None):
        self._parent = parent

    def __getitem__(self, key):
        try:
            return self._getitem(key)
        except KeyError:
            pass
        if self._parent is None:
            raise _KeyError(key)

        try:
            return self._parent[key]
        except KeyError:
            raise _KeyError(key)

class Environ(_DictWrapper):
    def __init__(self, parent=None, **kw):
        _DictWrapper.__init__(self, parent)
        self._dict = kw
        self._cache = {}

    def _getitem(self, key):
        try:
            return self._dict[key]
        except KeyError:
            pass
        try:
            return self._cache[key]
        except KeyError:
            pass
        fn = getattr(self, "_get_%s"%key, None)
        if fn is not None:
            try:
                self._cache[key] = rv = fn(self)
                return rv
            except _KeyError:
                raise KeyError(key)
        raise KeyError(key)

    def __setitem__(self, key, val):
        self._dict[key] = val

    def keys(self):
        s = set()
        s.update(self._dict.keys())
        s.update(self._cache.keys())
        if self._parent is not None:
            s.update(self._parent.keys())
        s.update(name[5:] for name in dir(self) if name.startswith("_get_"))
        return s

class IncluderDict(_DictWrapper):
    def __init__(self, parent, includePath=(".",)):
        _DictWrapper.__init__(self, parent)
        self._includePath = includePath
        self._st_mtime = 0

    def _getitem(self, key):
        if not key.startswith("include:"):
            raise KeyError(key)

        filename = key[len("include:"):]
        if os.path.isabs(filename):
            with open(filename, 'r') as f:
                stat = os.fstat(f.fileno())
                if stat.st_mtime > self._st_mtime:
                    self._st_mtime = stat.st_mtime
                return f.read()

        for elt in self._includePath:
            fullname = os.path.join(elt, filename)
            if os.path.exists(fullname):
                with open(fullname, 'r') as f:
                    stat = os.fstat(f.fileno())
                    if stat.st_mtime > self._st_mtime:
                        self._st_mtime = stat.st_mtime
                    return f.read()

        raise KeyError(key)

    def getUpdateTime(self):
        return self._st_mtime

class _BetterTemplate(string.Template):

    idpattern = r'[a-z0-9:_/\.\-]+'

    def __init__(self, template):
        string.Template.__init__(self, template)

class _FindVarsHelper(object):
    def __init__(self, dflts):
        self._dflts = dflts
        self._vars = set()
    def __getitem__(self, var):
        self._vars.add(var)
        try:
            return self._dflts[var]
        except KeyError:
            return ""

class Template(object):
    MAX_ITERATIONS = 32

    def __init__(self, pattern, includePath=(".",)):
        self._pat = pattern
        self._includePath = includePath

    def freevars(self, defaults=None):
        if defaults is None:
            defaults = {}
        d = _FindVarsHelper(defaults)
        self.format(d)
        return d._vars

    def format(self, values):
        values = IncluderDict(values, self._includePath)
        orig_val = self._pat
        nIterations = 0
        while True:
            v = _BetterTemplate(orig_val).substitute(values)
            if v == orig_val:
                return v
            orig_val = v
            nIterations += 1
            if nIterations > self.MAX_ITERATIONS:
                raise ValueError("Too many iterations in expanding template!")

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        import doctest
        doctest.testmod()
        print "done"
    else:
        for fn in sys.argv[1:]:
            with open(fn, 'r') as f:
                t = Template(f.read())
                print fn, t.freevars()

