from qtpy import QtCore as qc

class DataSource(qc.QObject):
    dataReady = qc.Signal(list)
    def __init__(self):
        super().__init__()
        self._index = 0
        self._layer = 0

    @property
    def index(self):
        return self._index
    @property
    def layer(self):
        return self._layer
    @property
    def name(self):
        return "base"
