import os
from qtpy import QtCore as qc
import re
import numpy as np

DETECTOR_MAP = {
    2560: {"name": "apa",    "splits": (800, 800, 960)},
    1600: {"name": "apauv",  "splits": (800, 800, 0)},
    800:  {"name": "apaind", "splits": (800, 0, 0)},
    960:  {"name": "apacol", "splits": (0, 0, 960)},
}


class FrameFileSource(qc.QObject):
    dataReady = qc.Signal(list)

    def __init__(self, filenames, index=0, name=None):
        super().__init__()
        self.files = filenames
        self.inventory = []
        self._index = index
        self._layer = 0
        self._name = name
        self._parse_files()

    def _parse_files(self):
        pattern = re.compile(r"^frame_(?P<tag>.+)_(?P<num>\d+)$")
        for f in self.files:
            if not os.path.exists(f):
                continue
            try:
                with np.load(f) as data:
                    current_items = []
                    for k in data.files:
                        m = pattern.match(k)
                        if m:
                            current_items.append((f, m.group('tag'), m.group('num')))
                    current_items.sort(key=lambda x: int(x[2]))
                    self.inventory.extend(current_items)
            except Exception as e:
                print(f"Error indexing {f}: {e}")

    @property
    def name(self):
        if self._name:
            return self._name
        if not self.inventory:
            if self.files:
                return os.path.basename(self.files[0])
            return "No data"
        fpath, tag, num = self.inventory[self._index]
        return f"{os.path.basename(fpath)} | {tag} [{num}]"

    @property
    def index(self):
        return self._index

    @property
    def layer(self):
        return self._layer

    def _generate(self):
        if not self.inventory:
            return
        fpath, tag, num = self.inventory[self._index]
        try:
            with np.load(fpath) as data:
                f_key, c_key, t_key = f"frame_{tag}_{num}", f"channels_{tag}_{num}", f"tickinfo_{tag}_{num}"
                raw_frame, raw_chans, tick_info = data[f_key], data[c_key], data[t_key]

                rows = raw_frame.shape[0]
                det = DETECTOR_MAP.get(rows, {"name": "unknown", "splits": (rows, 0, 0)})
                
                parts, cursor = [], 0
                for size in det['splits']:
                    if size > 0:
                        parts.append(dict(
                            samples=raw_frame[cursor:cursor+size, :],
                            channels=raw_chans[cursor:cursor+size],
                            tickinfo=tick_info))
                        cursor += size
                    else:
                        parts.append(None)
                
                self.dataReady.emit(parts)
        except Exception as e:
            print(f"Load error: {e}")

    @qc.Slot()
    def next(self):
        if self._index < len(self.inventory)-1:
            self._index += 1
            self._generate()

    @qc.Slot()
    def prev(self):
        if self._index > 0:
            self._index -= 1
            self._generate()
    @qc.Slot(int)
    def jump(self, idx):
        if 0 <= idx < len(self.inventory):
            self._index = idx
            self._generate()

