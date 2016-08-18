import sys, weakref

if "classes" not in globals():
    classes = weakref.WeakValueDictionary()
if "objects" not in globals():
    objects = weakref.WeakKeyDictionary()

def getQualName(cls):
    return cls.__module__ + "/" + cls.__name__

def reloadable(cls):
    qualName = getQualName(cls)
    if qualName in classes:
        oldCls = classes[qualName]

        exceptions = []

        temporaryRefs = list(objects[oldCls].values())
        for obj in objects[oldCls].values():
            try:
                obj.__class__ = cls
            except TypeError as e:
                exceptions.append(("While setting class for %s" % repr(e), e, sys.exc_info()[2]))
        del temporaryRefs

        objects[cls] = objects[oldCls]
        del objects[oldCls]

        for subcls in oldCls.__subclasses__():
            try:
                subcls.__bases__ = tuple(map(lambda supercls: cls if supercls is oldCls else supercls, subcls.__bases__))
            except TypeError as e:
                exceptions.append(("While setting base for '%s'" % getQualName(subcls), e, sys.exc_info()[2]))

        if len(exceptions):
            try:
                raise TypeError("".join(msg + ": " + e.args[0] for msg, e, tb in exceptions)).with_traceback(exceptions[0][2])
            finally:
                for msg, e, tb in exceptions:
                    del tb
    else:
        objects[cls] = weakref.WeakValueDictionary()
    classes[qualName] = cls

    oldinit = cls.__init__
    def init(self, *args, **kwargs):
        if self.__class__ is cls:
            objects[cls][id(self)] = self
        return oldinit(self, *args, **kwargs)
    cls.__init__ = init

    return cls
