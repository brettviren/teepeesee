from qtpy import QtCore as qc
import numpy as np
from .base import DataSource

class RandomDataSource(DataSource):
    def __init__(self, shapes):
        super().__init__()
        self.shapes = shapes 

    @property
    def name(self): return f"random_{self._index}"

    def _generate(self):
        outputs = []
        rng = np.random.default_rng(self._index)
        for h, w in self.shapes:
            data = rng.normal(loc=100, scale=10, size=(h, w)).astype(np.float32)
            for _ in range(rng.integers(1, 5)):
                row = rng.integers(0, h)
                data[row, :] += rng.uniform(20, 50)
            outputs.append(dict(samples=data,
                                channels=np.arange(data.shape[0]),
                                tickinfo=np.array([0, 1, data.shape[1]])))
        self.dataReady.emit(outputs)

    @qc.Slot()
    def next(self):
        self._index += 1
        self._generate()

    @qc.Slot()
    def prev(self):
        self._index = max(0, self._index - 1)
        self._generate()

    @qc.Slot(int)
    def jump(self, idx):
        self._index = max(0, idx)
        self._generate()

    @qc.Slot(int)
    def setLayer(self, layer):
        """Set the layer index. For RandomDataSource, this affects the random seed."""
        if self._layer != layer:
            self._layer = layer
            self._generate()
