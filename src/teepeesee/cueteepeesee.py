import sys
import os
import re
import json
import numpy as np
import PyQt6.QtWidgets as qw
import PyQt6.QtCore as qc
import PyQt6.QtGui as qg
import pyqtgraph as pg

# Environment: Debian/Linux, row-major (y, x)
pg.setConfigOption('imageAxisOrder', 'row-major')

SEISMIC_STOPS = {
    'ticks': [(0.0, (0, 0, 255, 255)),
              (0.5, (255, 255, 255, 255)),
              (1.0, (255, 0, 0, 255))],
    'mode': 'rgb'
}

DETECTOR_MAP = {
    2560: {"name": "apa",    "splits": (800, 800, 960)},
    1600: {"name": "apauv",  "splits": (800, 800, 0)},
    800:  {"name": "apaind", "splits": (800, 0, 0)},
    960:  {"name": "apacol", "splits": (0, 0, 960)},
}

# --- Data Sources ---

class DataSource(qc.QObject):
    dataReady = qc.pyqtSignal(list)
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

class FileSource(qc.QObject):
    dataReady = qc.pyqtSignal(list)
    
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
                    # Use FrameFileSource
                    self._delegate = FrameFileSource(self.files)
                else:
                    # Use TensorFileSource
                    self._delegate = TensorFileSource(self.files)
                
                # Connect delegate signals
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

    @qc.pyqtSlot()
    def next(self):
        if self._delegate:
            self._delegate.next()

    @qc.pyqtSlot()
    def prev(self):
        if self._delegate:
            self._delegate.prev()

    @qc.pyqtSlot(int)
    def jump(self, idx):
        if self._delegate:
            self._delegate.jump(idx)

    @qc.pyqtSlot(int)
    def setLayer(self, layer):
        if self._delegate and hasattr(self._delegate, 'setLayer'):
            self._delegate.setLayer(layer)

class FrameFileSource(qc.QObject):
    dataReady = qc.pyqtSignal(list)

    def __init__(self, filenames):
        super().__init__()
        self.files = filenames
        self.inventory = []
        self._index = 0
        self._layer = 0
        self._parse_files()

    def _parse_files(self):
        pattern = re.compile(r"^frame_(?P<tag>.+)_(?P<num>\d+)$")
        for f in self.files:
            if not os.path.exists(f): continue
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
        if not self.inventory:
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

    @qc.pyqtSlot()
    def next(self):
        if self._index < len(self.inventory)-1: self._index += 1; self._generate()
    @qc.pyqtSlot()
    def prev(self):
        if self._index > 0: self._index -= 1; self._generate()
    @qc.pyqtSlot(int)
    def jump(self, idx):
        if 0 <= idx < len(self.inventory): self._index = idx; self._generate()

class TensorFileSource(qc.QObject):
    dataReady = qc.pyqtSignal(list)

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
                meta_pattern = re.compile(r"^tensor_(?P<index>\d+)_(?P<plane>\d+)_metadata\.json$")
                
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
    
    @qc.pyqtSlot()
    def next(self):
        if self._index < len(self.inventory) - 1:
            self._index += 1
            self._generate()
    
    @qc.pyqtSlot()
    def prev(self):
        if self._index > 0:
            self._index -= 1
            self._generate()
    
    @qc.pyqtSlot(int)
    def jump(self, idx):
        if 0 <= idx < len(self.inventory):
            self._index = idx
            self._generate()

    @qc.pyqtSlot(int)
    def setLayer(self, layer):
        """Set the layer index for 3D arrays."""
        if self._layer != layer:
            self._layer = layer
            self._generate()

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
                row = rng.integers(0, h); data[row, :] += rng.uniform(20, 50)
            outputs.append(dict(samples=data,
                                channels=np.arange(data.shape[0]),
                                tickinfo=np.array([0, 1, data.shape[1]])))
        self.dataReady.emit(outputs)

    @qc.pyqtSlot()
    def next(self): self._index += 1; self._generate()
    @qc.pyqtSlot()
    def prev(self): self._index = max(0, self._index - 1); self._generate()
    @qc.pyqtSlot(int)
    def jump(self, idx): self._index = max(0, idx); self._generate()
    @qc.pyqtSlot(int)
    def setLayer(self, layer): self._layer = layer  # No-op for random data


class FrameTime(pg.PlotWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.curve = self.plot(pen='y', stepMode="center")

    def update_trace(self, data_slice):
        bins = np.arange(len(data_slice) + 1)
        # print(f'FrameTime: {bins.shape=} {data_slice.shape=}')
        self.curve.setData(x=bins, y=data_slice)


class FrameChan(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(100)
        self.curve = self.plot(pen='c', stepMode="center")

    def update_trace(self, data_slice):
        bins = np.arange(len(data_slice)-1)
        # print(f'FrameChan: {data_slice.shape=} {bins.shape=}')
        self.curve.setData(x=data_slice, y=bins)


class FrameInfo(qw.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: #00FF00; font-family: monospace; font-weight: bold; padding: 5px; border: 1px solid #555; border-radius: 4px;")
        self.setAttribute(qc.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def update_info(self, x, y, value, tickinfo=None):
        v_str = f"{value:.2f}" if isinstance(value, (float, np.float32)) else str(value)
        text = f"V: {v_str} ({int(x)},{int(y)})"

        if tickinfo is not None:
            start, period, _ = tickinfo
            dt = x * period
            current_t = start + dt
            text += f"T: {start*1e-6:,.1f} + {dt*1e-6:,.1f} = {current_t*1e-6:,.1f} ms @ {period} ns"
        #print(f'FrameInfo: {text}')
        self.setText(text)
        self.adjustSize()


class FrameImage(pg.PlotWidget):
    selectionChanged = qc.pyqtSignal(int, int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_item = pg.ImageItem()
        self.addItem(self.image_item)
        self.v_line = pg.InfiniteLine(angle=90, movable=True, pen='r')
        self.h_line = pg.InfiniteLine(angle=0, movable=True, pen='r')
        self.addItem(self.v_line, ignoreBounds=True)
        self.addItem(self.h_line, ignoreBounds=True)
        self.info_box = FrameInfo(self)
        self.v_line.sigDragged.connect(self.emit_selection)
        self.h_line.sigDragged.connect(self.emit_selection)
        self.scene().sigMouseClicked.connect(self.handle_click)

    def toggle_grid(self, state):
        self.showGrid(x=state, y=state, alpha=0.3)

    def set_lines(self, x, y):
        self.v_line.setValue(x); self.h_line.setValue(y)
        self.getViewBox().update()

    def emit_selection(self):
        self.selectionChanged.emit(int(self.v_line.value()),
                                   int(self.h_line.value()))

    def handle_click(self, event):
        if event.button() == qc.Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if self.image_item.sceneBoundingRect().contains(pos):
                pt = self.image_item.mapFromScene(pos)
                self.set_lines(pt.x(), pt.y()); self.emit_selection()

class FrameDisplay(qw.QWidget):
    userSelectionChanged = qc.pyqtSignal(int, int)
    def __init__(self):
        super().__init__()
        self.original_data = None
        self.baseline_data = None
        self._is_syncing = False
        self._rebaseline_active = False
        self._user_has_zoomed = False
        self._programmatic_range_change = False
        layout = qw.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.f_image = FrameImage()
        self.f_time = FrameTime()
        self.f_chan = FrameChan()
        self.f_hist = pg.HistogramLUTWidget()
        self.f_hist.setFixedWidth(100)
        self.f_hist.setImageItem(self.f_image.image_item)
        layout.addWidget(self.f_hist, 0, 0)
        layout.addWidget(self.f_image, 0, 1)
        layout.addWidget(self.f_chan, 0, 2)
        layout.addWidget(self.f_time, 1, 1)
        layout.setColumnStretch(1, 10)
        layout.setRowStretch(0, 10)
        self.f_time.setXLink(self.f_image); self.f_chan.setYLink(self.f_image)
        self.f_image.selectionChanged.connect(self._on_internal_change)
        self.f_image.getViewBox().sigRangeChanged.connect(self._on_range_changed)
        self.f_image.getViewBox().sigRangeChanged.connect(self.update_hist_region)

    @qc.pyqtSlot(np.ndarray)
    def updateData(self, samples=None, channels=None, tickinfo=None):
        self.current_channels = channels
        self.current_tickinfo = tickinfo
        self.original_data = samples
        self.baseline_data = samples - np.median(samples, axis=1, keepdims=True)
        self._apply_current_state()

    def _apply_current_state(self):
        if self.original_data is None: return
        data = self.baseline_data if self._rebaseline_active else self.original_data
        self.f_image.image_item.setImage(data, autoLevels=False)
        self.f_image.emit_selection()
        self.update_hist_region()

    def auto_contrast(self):
        data = self.f_image.image_item.image
        if data is None:
            return
        vb = self.f_image.getViewBox()
        rect = vb.viewRect()
        h, w = data.shape
        x0, x1 = int(np.clip(rect.left(), 0, w)), int(np.clip(rect.right(), 0, w))
        y0, y1 = int(np.clip(rect.top(), 0, h)), int(np.clip(rect.bottom(), 0, h))
        if (x1 - x0) < 2 or (y1 - y0) < 2:
            mn, mx = np.nanmin(data), np.nanmax(data)
        else:
            v_slice = data[y0:y1, x0:x1]
            mn, mx = np.nanmin(v_slice), np.nanmax(v_slice)
        if mn == mx:
            mx = mn + 1.0
        self.f_image.image_item.setLevels([mn, mx])
        self.f_hist.setLevels(mn, mx)

    def update_hist_region(self):
        data = self.f_image.image_item.image
        if data is None:
            return
        vb = self.f_image.getViewBox()
        rect = vb.viewRect()
        h, w = data.shape
        x0, x1 = int(np.clip(rect.left(), 0, w)), int(np.clip(rect.right(), 0, w))
        y0, y1 = int(np.clip(rect.top(), 0, h)), int(np.clip(rect.bottom(), 0, h))

        if x1 > x0 and y1 > y0:
            hist, bins = np.histogram(data[y0:y1, x0:x1], bins='auto')
            # When using "center" we must make sure x is one larger than y.  We
            # can do that here but the stepMode is "sticky" and later when we
            # update the image, this method does not get run but instead
            # HistogramULItem.imageChanged() gets run and that will use
            # .imageItem().getHistogram() with no trimming of x=bins.
            #
            # Blerg.            
            self.f_hist.item.plot.setData(x=bins[:-1], y=hist)# , stepMode="center")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "info_box"):
            self.info_box.move(self.width() - self.info_box.width() - 10, self.height() - self.info_box.height() - 10)

    def _on_internal_change(self, col, row):
        data = self.f_image.image_item.image
        if data is not None:
            h, w = data.shape
            c, r = int(np.clip(col, 0, w - 1)), int(np.clip(row, 0, h - 1))
            self.f_image.info_box.update_info(c, r, data[r, c],
                                              getattr(self, "current_tickinfo", None))
            self.f_time.update_trace(data[r, :])
            self.f_chan.update_trace(data[:, c])
        if not self._is_syncing: self.userSelectionChanged.emit(col, row)

    def set_crosshair(self, x, y):
        self.f_image.set_lines(x, y); self._on_internal_change(x, y)

    def set_vertical_crosshair(self, x):
        """Set only the vertical crosshair (x position), keeping horizontal independent."""
        y = int(self.f_image.h_line.value())
        self.f_image.v_line.setValue(x)
        self.f_image.getViewBox().update()
        self._on_internal_change(x, y)

    def _on_range_changed(self):
        """Track when user manually changes the view range."""
        if not self._programmatic_range_change:
            self._user_has_zoomed = True

    def reset_to_default_view(self):
        """Reset view with X-axis starting at 0 on the left."""
        data = self.f_image.image_item.image
        if data is not None:
            h, w = data.shape
            self._programmatic_range_change = True
            self.f_image.getViewBox().setRange(xRange=(0, w), yRange=(0, h), padding=0)
            self._programmatic_range_change = False
            self._user_has_zoomed = False

# --- Main Window ---

class MainWindow(qw.QMainWindow):
    def __init__(self, initial_files=None):
        super().__init__()
        self.setWindowTitle("Data Stack Analyzer")
        self.resize(1300, 950)
        self.current_source = None
        self.displays = []
        self.shapes = [(800, 1500), (800, 1500), (960, 1500)]

        container = qw.QWidget(); self.setCentralWidget(container)
        self.main_layout = qw.QVBoxLayout(container)
        for i in range(3):
            disp = FrameDisplay()
            self.main_layout.addWidget(disp); self.displays.append(disp)
            if i > 0: disp.f_image.setXLink(self.displays[0].f_image)
            disp.userSelectionChanged.connect(self.on_global_sync_request)

        self.status_bar = qw.QStatusBar(); self.setStatusBar(self.status_bar)
        self.init_menus_and_toolbar()
        self.set_cmap('viridis')
        
        if initial_files:
            self.load_file_source(initial_files)

    def init_menus_and_toolbar(self):
        mb = self.menuBar()
        file_m = mb.addMenu("&File")
        file_m.addAction(qg.QAction("File source...", self, shortcut="Ctrl+O", triggered=self.open_file_dialog))
        file_m.addAction(qg.QAction("Random source", self, triggered=self.init_random_source))
        file_m.addSeparator()
        file_m.addAction(qg.QAction("&Quit", self, shortcut="Ctrl+Q", triggered=self.close))

        view_m = mb.addMenu("&View")
        for t, k, s in [
                ("Home", "H", self.reset_view),
                ("Reset Zoom", "R", self.reset_zoom),
                ("Auto-Contrast", "A", self.auto_contrast_all)]:
            view_m.addAction(qg.QAction(t, self, shortcut=k, triggered=s))

        grid_act = qg.QAction("Toggle Grid", self, checkable=True, shortcut="G")
        grid_act.triggered.connect(self.toggle_grids)
        view_m.addAction(grid_act)

        cmap_m = view_m.addMenu("Colormap")
        cmaps = [("Viridis", "viridis", "C, V"),
                 ("Seismic", "seismic", "C, S"),
                 ("Grayscale", "grey", "C, G"),
                 ("Rainbow", "spectrum", "C, R")]
        for n, p, s in cmaps:
            a = qg.QAction(n, self, shortcut=qg.QKeySequence(s))
            a.triggered.connect(self._make_cmap_handler(p))
            cmap_m.addAction(a)

        data_m = mb.addMenu("&Data")
        rebase_act = qg.QAction("Rebaseline", self, checkable=True, shortcut='B')
        rebase_act.triggered.connect(self.toggle_baselines)
        data_m.addAction(rebase_act)


        toolbar = self.addToolBar("Navigation")
        self.prev_btn = qw.QPushButton("Prev")
        toolbar.addWidget(self.prev_btn)
        self.next_btn = qw.QPushButton("Next")
        toolbar.addWidget(self.next_btn)
        toolbar.addSeparator()
        toolbar.addWidget(qw.QLabel(" Layer: "))
        self.layer_spinbox = qw.QSpinBox()
        self.layer_spinbox.setMinimum(0)
        self.layer_spinbox.setMaximum(999)
        self.layer_spinbox.setValue(0)
        self.layer_spinbox.setFixedWidth(60)
        toolbar.addWidget(self.layer_spinbox)
        toolbar.addSeparator()
        toolbar.addWidget(qw.QLabel(" Jump: "))
        self.idx_input = qw.QLineEdit(); self.idx_input.setFixedWidth(60)
        self.idx_input.setValidator(qg.QIntValidator(0, 999999))
        self.idx_input.returnPressed.connect(self.on_jump_requested)
        toolbar.addWidget(self.idx_input)

    def open_file_dialog(self):
        files, _ = qw.QFileDialog.getOpenFileNames(self, "Open Data Files", "", "Numpy Zipped (*.npz)")
        if files: self.load_file_source(files)

    def load_file_source(self, filenames):
        self.current_source = FileSource(filenames)
        self._connect_source()
        if self.current_source._delegate:
            self.current_source._delegate._generate()

    def init_random_source(self):
        self.current_source = RandomDataSource(self.shapes)
        self._connect_source()
        self.current_source._generate()

    def _connect_source(self):
        # Disconnect previous if any
        try:
            self.prev_btn.clicked.disconnect()
        except:
            # print("Failed to disconnect prev button")
            pass
        try:
            self.next_btn.clicked.disconnect()
        except:
            # print("Failed to disconnect next button")
            pass
        try:
            self.layer_spinbox.valueChanged.disconnect()
        except:
            # print("Failed to disconnect layer spinbox")
            pass

        self.prev_btn.clicked.connect(self.current_source.prev)
        self.next_btn.clicked.connect(self.current_source.next)
        self.layer_spinbox.valueChanged.connect(self.current_source.setLayer)
        self.current_source.dataReady.connect(self.distribute_data)
        self.current_source.dataReady.connect(self.update_ui)

    def on_jump_requested(self):
        if self.current_source:
            try:
                self.current_source.jump(int(self.idx_input.text()))
            except ValueError:
                print(f'Failed to jump to {self.idx_input.text()}')

    @qc.pyqtSlot(list)
    def distribute_data(self, data):
        is_initial_load = all(d.original_data is None for d in self.displays)
        # Note: If FileSource only has one array per index, we distribute it
        # to the first display, or however you'd like to handle multiple displays.
        for i, datum in enumerate(data):
            if i < len(self.displays):
                self.displays[i].updateData(**datum)

        # Reset view only if no display has been manually zoomed by user
        if not any(d._user_has_zoomed for d in self.displays):
            self.reset_view()

        if is_initial_load:
            qc.QTimer.singleShot(50, self.auto_contrast_all)
        else:
            self.auto_contrast_all()

    def update_ui(self):
        if self.current_source:
            self.status_bar.showMessage(f"Source: {self.current_source.name}")
            self.idx_input.setText(str(self.current_source.index))
            self.layer_spinbox.blockSignals(True)
            self.layer_spinbox.setValue(self.current_source.layer)
            self.layer_spinbox.blockSignals(False)

    def reset_view(self):
        """Reset all displays to default view with X starting at 0."""
        for d in self.displays:
            d.reset_to_default_view()

    def reset_zoom(self):
        """Reset zoom to default view with X starting at 0."""
        for d in self.displays:
            d.reset_to_default_view()

    def auto_contrast_all(self):
        [d.auto_contrast() for d in self.displays]

    def set_cmap(self, p):
        for d in self.displays:
            if p == 'seismic':
                d.f_hist.gradient.restoreState(SEISMIC_STOPS)
            else:
                d.f_hist.gradient.loadPreset(p)
            d.f_hist.regionChanged()

    def _make_cmap_handler(self, p):
        return lambda: self.set_cmap(p)

    def toggle_grids(self, s):
        [d.f_image.toggle_grid(s) for d in self.displays]

    def toggle_baselines(self, s): 
        for d in self.displays:
            d._rebaseline_active = s
            d._apply_current_state()

    def on_global_sync_request(self, col, row):
        src = self.sender()
        for d in self.displays:
            if d != src:
                d._is_syncing = True
                d.set_vertical_crosshair(col)
                d._is_syncing = False

def main():
    app = qw.QApplication(sys.argv)
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    window = MainWindow(initial_files=files)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
