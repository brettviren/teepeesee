
import os
import numpy as np
from qtpy import QtCore as qc

from .frame import FrameFileSource
from .tensor import TensorFileSource

class FileSource(qc.QObject):
    dataReady = qc.Signal(list)
    
    def __init__(self, filenames):
        super().__init__()
        self.files = filenames
        self._delegate = None
        self._detect_and_create_delegate()
    
    def _detect_and_create_delegate(self):
        """Detect schema from first file and create appropriate delegate."""
        if not self.files:
            return
        
        first_file = self.files[0]
        if not os.path.exists(first_file):
            return
        
        try:
            with np.load(first_file) as data:
                keys = data.files
                
                # Check if this is a frame schema file
                has_frame_keys = any(k.startswith('frame_') for k in keys)
                has_channels_keys = any(k.startswith('channels_') for k in keys)
                has_tickinfo_keys = any(k.startswith('tickinfo_') for k in keys)
                
                if has_frame_keys and has_channels_keys and has_tickinfo_keys:
                    self._delegate = FrameFileSource(self.files)
                else:
                    self._delegate = TensorFileSource(self.files)
                
                self._delegate.dataReady.connect(self.dataReady.emit)
                
        except Exception as e:
            print(f"Error detecting schema in {first_file}: {e}")
    
    @property
    def name(self):
        if self._delegate:
            return self._delegate.name
        return "No data"
    
    @property
    def index(self):
        if self._delegate:
            return self._delegate.index
        return 0

    @property
    def layer(self):
        if self._delegate and hasattr(self._delegate, 'layer'):
            return self._delegate.layer
        return 0

    @qc.Slot()
    def next(self):
        if self._delegate:
            self._delegate.next()

    @qc.Slot()
    def prev(self):
        if self._delegate:
            self._delegate.prev()

    @qc.Slot(int)
    def jump(self, idx):
        if self._delegate:
            self._delegate.jump(idx)

    @qc.Slot(int)
    def setLayer(self, layer):
        if self._delegate and hasattr(self._delegate, 'setLayer'):
            self._delegate.setLayer(layer)

