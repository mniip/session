from Reload import reloadable

@reloadable
class State:
    def __init__(self, state):
        self.current_state = state

    def set_state(self, state):
        self.current_state = state

    def get_state(self):
        return self.current_state

def equals(state, exception = RuntimeError, message = "{self!r} is in state {actual!r}, expected {expected!r}"):
    def decorator(fun):
        def ret(self, *args, **kwargs):
            if self.get_state() == state:
                return fun(self, *args, **kwargs)
            else:
                raise exception(message.format(self = self, actual = self.get_state(), expected = state))
        return ret
    return decorator

def any_of(states, exception = RuntimeError, message = "{self!r} is in state {actual!r}, expected any of {expected!r}"):
    def decorator(fun):
        def ret(self, *args, **kwargs):
            if self.get_state() in states:
                return fun(self, *args, **kwargs)
            else:
                raise exception(message.format(self = self, actual = self.get_state(), expected = states))
        return ret
    return decorator

def isnt(state, exception = RuntimeError, message = "{self!r} is in state {actual!r}, expected not {expected!r}"):
    def decorator(fun):
        def ret(self, *args, **kwargs):
            if self.get_state() != state:
                return fun(self, *args, **kwargs)
            else:
                raise exception(message.format(self = self, actual = self.get_state(), expected = state))
        return ret
    return decorator

def none_of(states, exception = RuntimeError, message = "{self!r} is in state {actual!r}, expected none of {expected!r}"):
    def decorator(fun):
        def ret(self, *args, **kwargs):
            if self.get_state() not in states:
                return fun(self, *args, **kwargs)
            else:
                raise exception(message.format(self = self, actual = self.get_state(), expected = states))
        return ret
    return decorator
