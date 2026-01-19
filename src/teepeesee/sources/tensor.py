import os
from qtpy import QtCore as qc
import re
import numpy as np
import json

class TensorFileSource(qc.QObject):
    dataReady = qc.Signal(list)

    def __init__(self, filenames):
        super().__init__()
        self.files = filenames
        self.inventory = []  # List of (filepath, index) tuples
        self._index = 0
        self._layer = 0
        self._parse_files()
        print(f'TensorFileSource: {self.name}')
    
    def _parse_files(self):
        """Parse files and build inventory of unique INDEX values."""
        array_pattern = re.compile(r"^tensor_(?P<index>\d+)_(?P<plane>\d+)_array$")
        indices_set = set()
        
        for f in self.files:
            if not os.path.exists(f):
                print(f'no such file: {f}')
                continue
            try:
                with np.load(f) as data:
                    for k in data.files:
                        #print(f'checking file: {k}')
                        m = array_pattern.match(k)
                        if m:
                            idx = int(m.group('index'))
                            indices_set.add((f, idx))
            except Exception as e:
                print(f"Error indexing {f}: {e}")
        
        # Sort by index
        self.inventory = sorted(list(indices_set), key=lambda x: x[1])

    @property
    def name(self):
        if not self.inventory:
            return "No data"
        fpath, idx = self.inventory[self._index]
        return f"{os.path.basename(fpath)} | tensor [{idx}]"

    @property
    def index(self):
        return self._index

    @property
    def layer(self):
        return self._layer
    
    def _generate(self):
        """Load all planes for the current index and create separate parts."""
        if not self.inventory:
            return
        
        fpath, target_index = self.inventory[self._index]
        
        try:
            with np.load(fpath) as data:
                # Find all arrays and metadata for this index
                array_pattern = re.compile(r"^tensor_(?P<index>\d+)_(?P<plane>\d+)_array$")
                
                # Collect arrays and metadata by plane
                planes_data = {}  # plane_num -> (array, metadata)
                
                for k in data.files:
                    array_match = array_pattern.match(k)
                    if array_match and int(array_match.group('index')) == target_index:
                        plane_num = int(array_match.group('plane'))
                        array = data[k]

                        # Handle 3D arrays by using the layer property
                        if array.ndim == 3:
                            # Clip layer to valid range
                            layer_idx = min(self._layer, array.shape[0] - 1)
                            layer_idx = max(0, layer_idx)
                            array = array[layer_idx, :, :]

                        # Find corresponding metadata
                        meta_key = f"tensor_{target_index}_{plane_num}_metadata.json"
                        metadata = None
                        if meta_key in data.files:
                            metadata = json.loads(data[meta_key].decode())

                        planes_data[plane_num] = (array, metadata)
                
                # Sort by plane number
                sorted_planes = sorted(planes_data.items())
                
                if not sorted_planes:
                    return
                
                # Create parts list with one part per plane
                parts = []
                for plane_num, (array, metadata) in sorted_planes:
                    # Generate synthetic channels
                    num_channels = array.shape[0]
                    channels = np.arange(num_channels)
                    
                    # Extract tickinfo from metadata
                    if metadata and 'time' in metadata and 'period' in metadata:
                        time_start = metadata['time']
                        period = metadata['period']
                        num_ticks = array.shape[1]
                        tickinfo = np.array([time_start, period, num_ticks])
                    else:
                        # Default tickinfo
                        num_ticks = array.shape[1]
                        tickinfo = np.array([0, 1, num_ticks])
                    
                    parts.append(dict(
                        samples=array,
                        channels=channels,
                        tickinfo=tickinfo
                    ))
                
                self.dataReady.emit(parts)
                
        except Exception as e:
            print(f"Load error: {e}")
            import traceback
            traceback.print_exc()
    
    @qc.Slot()
    def next(self):
        if self._index < len(self.inventory) - 1:
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

    @qc.Slot(int)
    def setLayer(self, layer):
        """Set the layer index for 3D arrays."""
        if self._layer != layer:
            self._layer = layer
            self._generate()

