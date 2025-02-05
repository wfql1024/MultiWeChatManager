

class GlobalMembers:
    _instance = None
    _root_class = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def root_class(self):
        return self._root_class

    @root_class.setter
    def root_class(self, value):
        self._root_class = value



