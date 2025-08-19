'''
工厂类
生产AllocateAction

'''

class AllocateFactory:
    """A Factory"""

    def __init__(self):
        self._registry = {}

    def register(self, name, cls):
        """Register a class with the factory"""
        self._registry[name] = cls

    def allocate_get(self, name, *args, **kwargs):
        """Get an instance of the registered class"""
        cls = self._registry.get(name)
        if cls is None:
            raise ValueError(f"No class registered with name: {name}")
        instance = cls(*args, **kwargs)
        return instance