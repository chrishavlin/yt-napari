import weakref

import yt

from yt_napari.logging import ytnapari_log


class DatasetCache:
    def __init__(self):
        self.available = {}
        self._most_recent: str = None

    def add_ds(self, ds, name: str):
        if name in self.available:
            ytnapari_log.warning(f"A dataset already exists for {name}. Overwriting.")
        self.available[name] = weakref.proxy(ds)
        self._most_recent = name

    @property
    def most_recent(self):
        if self._most_recent is not None:
            return self.available[self._most_recent]
        return None

    def get_ds(self, name: str):
        if self.exists(name):
            return self.available[name]
        ytnapari_log.warning(f"{name} not found in cache.")
        return None

    def exists(self, name: str):
        return name in self.available

    def rm_ds(self, name: str):
        self.available.pop(name, None)

    def rm_all(self):
        self.available = {}

    def check_then_load(self, filename: str):
        if self.exists(filename) is False:
            ds = yt.load(filename)
            self.add_ds(ds, filename)
        return self.get_ds(filename)


dataset_cache = DatasetCache()
