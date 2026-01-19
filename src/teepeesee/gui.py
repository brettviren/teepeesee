from qtpy import QtCore as qc
from qtpy import QtWidgets as qw
from qtpy import QtGui as qg
from .displays import FrameDisplay
from .sources.file import FileSource
from .sources.random import RandomDataSource

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
        self.current_source = None
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
        self.idx_input = qw.QLineEdit()
        self.idx_input.setFixedWidth(60)
        self.idx_input.setValidator(qg.QIntValidator(0, 999999))
        self.idx_input.returnPressed.connect(self.on_jump_requested)
        toolbar.addWidget(self.idx_input)

    def open_file_dialog(self):
        files, _ = qw.QFileDialog.getOpenFileNames(self, "Open Data Files", "", "Numpy Zipped (*.npz)")
        if files:
            self.load_file_source(files)

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

    @qc.Slot(list)
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
            if d == src:
                d._is_syncing = True
                d.set_vertical_crosshair(col)
                d._is_syncing = False

