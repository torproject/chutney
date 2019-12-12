# Future imports for Python 2.7, mandatory in 3.0
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

def memoized(fn):
    """Decorator: memoize a function."""
    memory = {}
    def memoized_fn(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        try:
            result = memory[key]
        except KeyError:
            result = memory[key] = fn(*args, **kwargs)
        return result
    return memoized_fn
