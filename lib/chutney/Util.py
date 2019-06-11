

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
