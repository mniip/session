from Reload import reloadable
import yaml

config_file = "config.yaml"

@reloadable
class Query:
    def __init__(self, path):
        self.path = path

    def run(self):
        obj = self.__class__.store
        for key in self.path:
            obj = obj[key]
        return obj
    
    def index(self, key):
        return self.__class__(self.path + [key])

    def __repr__(self):
        return self.__class__.__name__ + "(" + repr(self.path) + ") <" + repr(self.run()) + ">"

    def __len__(self):
        return len(self.run())

    def __getitem__(self, key):
        target = self.run()[key]
        if isinstance(target, dict) or isinstance(target, list) or isinstance(target, tuple):
            return self.index(key)
        else:
            return target

    def get(self, key, default = None):
        obj = self.run()
        if key in obj:
            return self[key]
        else:
            return default

    def __iter__(self):
        for value in self.run():
            yield value

    def __reversed__(self):
        return reversed(self.run())

    def __contains__(self, item):
        return item in self.run()

    def copy(self):
        return self.run().copy()

    def items(self):
        return self.run().items()

    def keys(self):
        return self.run().keys()

    def values(self):
        return self.run().values()

with open(config_file) as f:
    @reloadable
    class ConfigQuery(Query):
        store = yaml.load(f)

    config = ConfigQuery([])
