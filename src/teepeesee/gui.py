from qtpy import QtCore as qc
from qtpy import QtWidgets as qw
from qtpy import QtGui as qg
from .displays import FrameDisplay
from .sources.file import FileSource
from .sources.random import RandomDataSource
from .sources.base import SourceManager

SEISMIC_STOPS = {
    'ticks': [(0.0, (0, 0, 255, 255)),
              (0.5, (255, 255, 255, 255)),
              (1.0, (255, 0, 0, 255))],
    'mode': 'rgb'
}

class MainWindow(qw.QMainWindow):
    def __init__(self, initial_files=None):
        super().__init__()
        self.setWindowTitle("Data Stack Analyzer")
        self.resize(1300, 950)
        self.source_manager = SourceManager()
        self.displays = []
        self.shapes = [(800, 1500), (800, 1500), (960, 1500)]

        container = qw.QWidget()
        self.setCentralWidget(container)
        self.main_layout = qw.QVBoxLayout(container)
        for i in range(3):
            disp = FrameDisplay()
            self.main_layout.addWidget(disp)
            self.displays.append(disp)
            if i > 0:
                disp.f_image.setXLink(self.displays[0].f_image)
            disp.userSelectionChanged.connect(self.on_global_sync_request)

        self.status_bar = qw.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.init_menus_and_toolbar()
        self.set_cmap('viridis')

        # Connect source_manager to UI
        self._connect_source_manager()

        if initial_files:
            self._load_initial_files(initial_files)

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
                 ("Rainbow", "spectrum", "C, R"),
                 ("RGB Multi", "rgb_multi", "C, M")]
        for n, p, s in cmaps:
            a = qg.QAction(n, self, shortcut=qg.QKeySequence(s))
            a.triggered.connect(self._make_cmap_handler(p))
            cmap_m.addAction(a)

        data_m = mb.addMenu("&Data")
        rebase_act = qg.QAction("Rebaseline", self, checkable=True, shortcut='B')
        rebase_act.triggered.connect(self.toggle_baselines)
        data_m.addAction(rebase_act)

        # Source cycling shortcuts
        prev_source_act = qg.QAction("Previous Source", self, shortcut="PgUp", triggered=self.prev_source)
        next_source_act = qg.QAction("Next Source", self, shortcut="PgDown", triggered=self.next_source)
        data_m.addSeparator()
        data_m.addAction(prev_source_act)
        data_m.addAction(next_source_act)


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
        toolbar.addWidget(qw.QLabel(" Source: "))
        self.source_combo = qw.QComboBox()
        self.source_combo.setMinimumWidth(150)
        toolbar.addWidget(self.source_combo)
        toolbar.addSeparator()
        toolbar.addWidget(qw.QLabel(" Jump: "))
        self.idx_input = qw.QLineEdit()
        self.idx_input.setFixedWidth(60)
        self.idx_input.setValidator(qg.QIntValidator(0, 999999))
        self.idx_input.returnPressed.connect(self.on_jump_requested)
        toolbar.addWidget(self.idx_input)

    def open_file_dialog(self):
        files, _ = qw.QFileDialog.getOpenFileNames(self, "Open Data Files", "", "Numpy Zipped (*.npz)")
        if files:
            self.load_file_source(files)

    def _load_initial_files(self, initial_files):
        """Parse initial_files and load them as sources.

        Format: "name:filename" or "filename"
        Files with the same name are grouped together.
        Files without a name are loaded individually.
        """
        from collections import defaultdict

        # Group files by name
        named_groups = defaultdict(list)
        unnamed_files = []

        for entry in initial_files:
            if ':' in entry:
                # Split on first colon only
                name, filename = entry.split(':', 1)
                named_groups[name].append(filename)
            else:
                unnamed_files.append(entry)

        # Load named groups
        for name, filenames in named_groups.items():
            self.load_file_source(filenames, name=name)

        # Load unnamed files individually
        for filename in unnamed_files:
            self.load_file_source([filename])

    def load_file_source(self, filenames, name=None):
        source = FileSource(filenames, self.source_manager.index, name)
        self.source_manager.add_source(source)
        if source._delegate:
            source._delegate._generate()

    def init_random_source(self):
        source = RandomDataSource(self.shapes, self.source_manager.index)
        self.source_manager.add_source(source)
        source._generate()

    def _connect_source_manager(self):
        """Connect the source_manager to UI elements."""
        self.prev_btn.clicked.connect(self.source_manager.prev)
        self.next_btn.clicked.connect(self.source_manager.next)
        self.layer_spinbox.valueChanged.connect(self.source_manager.setLayer)
        self.source_manager.dataReady.connect(self.distribute_data)
        self.source_manager.dataReady.connect(self.update_ui)
        self.source_manager.indexChanged.connect(self.on_index_changed)
        self.source_manager.sourceAdded.connect(self.on_source_added)
        self.source_manager.sourceSelected.connect(self.on_source_selected)
        self.source_combo.currentTextChanged.connect(self.on_source_combo_changed)

    def on_jump_requested(self):
        try:
            self.source_manager.jump(int(self.idx_input.text()))
        except ValueError:
            print(f'Failed to jump to {self.idx_input.text()}')

    @qc.Slot(int)
    def on_index_changed(self, index):
        """Update UI when source_manager index changes."""
        self.idx_input.setText(str(index))

    @qc.Slot(object)
    def on_source_added(self, source):
        """Called when a source is added to the manager."""
        # Add source name to the dropdown
        self.source_combo.addItem(source.name)
        # Select it if it's the first source
        if self.source_combo.count() == 1:
            self.source_combo.setCurrentIndex(0)

    @qc.Slot(object)
    def on_source_selected(self, source):
        """Called when a source is selected in the manager."""
        # Update the dropdown to match (without triggering signal)
        self.source_combo.blockSignals(True)
        index = self.source_combo.findText(source.name)
        if index >= 0:
            self.source_combo.setCurrentIndex(index)
        self.source_combo.blockSignals(False)

    @qc.Slot(str)
    def on_source_combo_changed(self, name):
        """Called when user changes the source dropdown."""
        if name:
            self.source_manager.select_source(name)

    def prev_source(self):
        """Cycle to previous source in the dropdown."""
        if self.source_combo.count() > 0:
            current_idx = self.source_combo.currentIndex()
            new_idx = (current_idx - 1) % self.source_combo.count()
            self.source_combo.setCurrentIndex(new_idx)

    def next_source(self):
        """Cycle to next source in the dropdown."""
        if self.source_combo.count() > 0:
            current_idx = self.source_combo.currentIndex()
            new_idx = (current_idx + 1) % self.source_combo.count()
            self.source_combo.setCurrentIndex(new_idx)

    @qc.Slot(list)
    def distribute_data(self, data):
        is_initial_load = all(d.original_data is None for d in self.displays)

        # Check if we're in RGB Multi mode
        rgb_multi_mode = any(d._rgb_multi_mode for d in self.displays)

        if rgb_multi_mode:
            # RGB Multi mode: get data from all sources
            self._redistribute_for_rgb_multi()
        else:
            # Normal mode: use data from current source
            # Update displays that have data
            for i, datum in enumerate(data):
                if i < len(self.displays):
                    self.displays[i].updateData(**datum)

            # Clear displays that don't have data in this source
            for i in range(len(data), len(self.displays)):
                self.displays[i].clear()

        # Reset view only if no display has been manually zoomed by user
        if not any(d._user_has_zoomed for d in self.displays):
            self.reset_view()

        if is_initial_load:
            qc.QTimer.singleShot(50, self.auto_contrast_all)
        else:
            self.auto_contrast_all()

    def update_ui(self):
        self.status_bar.showMessage(f"Source: {self.source_manager.name}")
        self.idx_input.setText(str(self.source_manager.index))
        self.layer_spinbox.blockSignals(True)
        self.layer_spinbox.setValue(self.source_manager.layer)
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
        if p == 'rgb_multi':
            # Enable RGB Multi mode
            for d in self.displays:
                d.set_rgb_multi_mode(True)
            # Re-distribute data in RGB Multi mode
            self._redistribute_for_rgb_multi()
        else:
            # Disable RGB Multi mode and set normal colormap
            for d in self.displays:
                d.set_rgb_multi_mode(False)
                if p == 'seismic':
                    d.f_hist.gradient.restoreState(SEISMIC_STOPS)
                else:
                    d.f_hist.gradient.loadPreset(p)
                d.f_hist.regionChanged()
            # Re-distribute data in normal mode
            self._redistribute_normal()

    def _make_cmap_handler(self, p):
        return lambda: self.set_cmap(p)

    def _redistribute_for_rgb_multi(self):
        """Redistribute data from all sources for RGB Multi mode."""
        # Get data from all sources (up to 3)
        all_sources_data = self.source_manager.get_all_sources_data()

        # Group data by part index
        max_parts = max(len(source_data) for source_data in all_sources_data) if all_sources_data else 0

        for part_idx in range(max_parts):
            if part_idx < len(self.displays):
                # Collect data for this part from all sources
                part_data_list = []
                for source_data in all_sources_data[:3]:  # Max 3 sources
                    if part_idx < len(source_data):
                        part_data_list.append(source_data[part_idx])

                if part_data_list:
                    self.displays[part_idx].updateMultiData(part_data_list)
                else:
                    self.displays[part_idx].clear()

        # Clear remaining displays
        for i in range(max_parts, len(self.displays)):
            self.displays[i].clear()

    def _redistribute_normal(self):
        """Redistribute data from current source in normal mode."""
        # Get data from the current source only
        current_data = self.source_manager.get_current_source_data()

        for i, datum in enumerate(current_data):
            if i < len(self.displays):
                self.displays[i].updateData(**datum)

        # Clear displays beyond current data
        for i in range(len(current_data), len(self.displays)):
            self.displays[i].clear()

    def toggle_grids(self, s):
        [d.f_image.toggle_grid(s) for d in self.displays]

    def toggle_baselines(self, s): 
        for d in self.displays:
            d._rebaseline_active = s
            d._apply_current_state()

    def on_global_sync_request(self, col, row):
        src = self.sender()
        for d in self.displays:
            if d == src:
                d._is_syncing = True
                d.set_vertical_crosshair(col)
                d._is_syncing = False

