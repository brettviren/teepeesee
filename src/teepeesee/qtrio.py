import numpy as np
from typing import List, Optional, Tuple, Dict

# Import PyQt and PyQtGraph components
# Assuming PyQt5 is used, as it is common with pyqtgraph installations.
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# Assuming Frame is importable from teepeesee.io
from .io import Frame

# Set PyQtGraph configuration for white background/black foreground
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

class QtTrioDisplay(QtWidgets.QWidget):
    """
    Provides an interactive display for Frame data using PyQt and PyQtGraph, 
    splitting the visualization into three separate channel planes for independent 
    scaling and zooming.
    """
    N_PLANES = 3
    # Mapping common names to PyQtGraph colormaps (or equivalents)
    AVAILABLE_CMAPS = ["viridis", "seismic", "rainbow"] 

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._current_frame: Optional[Frame] = None
        self._plane_sizes: List[int] = []
        self._plane_offsets: List[int] = []
        
        # State variables for controls
        self._current_cmap_name: str = self.AVAILABLE_CMAPS[0]
        self._median_subtraction_active: bool = False
        
        # Global indices for selected point
        self._selected_global_row: int = 0
        self._selected_col: int = 0
        
        # PyQtGraph components storage
        self._image_views: List[Optional[pg.ImageView]] = [None] * self.N_PLANES
        self._col_plots: List[Optional[pg.PlotWidget]] = [None] * self.N_PLANES
        self._row_plot: Optional[pg.PlotWidget] = None
        
        # Plot data handles
        self._row_line_handle: Optional[pg.PlotDataItem] = None
        self._col_line_handles: List[Optional[pg.PlotDataItem]] = [None] * self.N_PLANES
        
        # Cursor handles (InfiniteLines)
        self._v_cursors: List[Optional[pg.InfiniteLine]] = [None] * self.N_PLANES # Vertical in images
        self._h_cursors: List[Optional[pg.InfiniteLine]] = [None] * self.N_PLANES # Horizontal in column plots
        self._row_v_cursor: Optional[pg.InfiniteLine] = None # Vertical in row plot
        
        self._setup_ui()

    def _setup_ui(self):
        """Initializes the main layout and widgets."""
        self.setWindowTitle("Teepeesee Trio Display (PyQtGraph)")
        
        main_layout = QtWidgets.QHBoxLayout(self)
        
        # 1. Graphics Layout (Left side: Images and Plots)
        # Use GraphicsLayoutWidget for flexible grid layout of plots
        self._glw = pg.GraphicsLayoutWidget()
        main_layout.addWidget(self._glw, stretch=3)
        
        # 2. Control Panel (Right side)
        control_panel = QtWidgets.QWidget()
        control_layout = QtWidgets.QVBoxLayout(control_panel)
        control_layout.setAlignment(QtCore.Qt.AlignTop)
        main_layout.addWidget(control_panel, stretch=1)
        
        # --- Controls ---
        
        # Median Subtraction Checkbox (Replaces Matplotlib CheckButtons)
        self._median_checkbox = QtWidgets.QCheckBox("Subtract Median")
        self._median_checkbox.stateChanged.connect(self._toggle_median_subtraction)
        control_layout.addWidget(self._median_checkbox)
        
        # Colormap Selection (Replaces Matplotlib RadioButtons)
        cmap_group = QtWidgets.QGroupBox("Colormap")
        cmap_layout = QtWidgets.QVBoxLayout(cmap_group)
        self._cmap_buttons = []
        for i, cmap_name in enumerate(self.AVAILABLE_CMAPS):
            btn = QtWidgets.QRadioButton(cmap_name)
            # Use partial function application via lambda to pass the name
            btn.toggled.connect(lambda checked, name=cmap_name: self._set_cmap(name) if checked else None)
            cmap_layout.addWidget(btn)
            self._cmap_buttons.append(btn)
            if i == 0:
                btn.setChecked(True)
        control_layout.addWidget(cmap_group)
        
        # Spacer
        control_layout.addStretch(1)
        
        self.resize(1200, 800)

    def _setup_graphics_layout(self, plane_sizes: List[int]):
        """Sets up the PyQtGraph plotting widgets based on plane sizes."""
        
        # Clear existing items if resizing/reinitializing
        self._glw.clear()
        self._image_views = [None] * self.N_PLANES
        self._col_plots = [None] * self.N_PLANES
        
        total_channels = sum(plane_sizes)
        
        # 1. Setup Image Views and Column Plots
        for i in range(self.N_PLANES):
            if plane_sizes[i] == 0:
                continue

            # Image View (Column 0)
            imv = pg.ImageView(self._glw)
            imv.getView().invertY(False) # Y increases upwards (Channel index 0 at bottom)
            imv.getView().setAspectLocked(False)
            imv.getView().setTitle(f"Plane {i}")
            
            # Connect mouse click event for cursor update
            # We connect to the ImageItem itself to get local coordinates easily
            imv.getImageItem().mouseClickEvent = lambda ev, idx=i: self._on_image_click(ev, idx)
            
            self._image_views[i] = imv
            self._glw.addItem(imv, row=i, col=0)
            
            # Column Profile Plot (Column 1)
            col_plot = pg.PlotWidget(title=f"Plane {i} Profile")
            col_plot.setLabel('bottom', 'Amplitude')
            col_plot.setLabel('left', 'Channels')
            col_plot.showGrid(x=True, y=True)
            
            # Link Y axis of image and column plot
            col_plot.setYLink(imv.getViewBox())
            
            self._col_plots[i] = col_plot
            self._glw.addItem(col_plot, row=i, col=1)
            
            # Add vertical cursor to image view
            v_cursor = pg.InfiniteLine(movable=False, angle=90, pen='r')
            imv.getView().addItem(v_cursor)
            self._v_cursors[i] = v_cursor
            
            # Add horizontal cursor to column plot
            h_cursor = pg.InfiniteLine(movable=False, angle=0, pen='r')
            col_plot.addItem(h_cursor)
            self._h_cursors[i] = h_cursor
            
            # Set row height ratio based on channel count
            self._glw.getRow(i).setHeight(plane_sizes[i])
            
            # Hide X axis for upper plots
            if i < self.N_PLANES - 1:
                imv.getView().getAxis('bottom').setTicks([])
                
        # 2. Setup Row Plot (Bottom row, spans Column 0)
        self._row_plot = pg.PlotWidget(title="Row Profile")
        self._row_plot.setLabel('bottom', 'Ticks')
        self._row_plot.setLabel('left', 'Amplitude')
        self._row_plot.showGrid(x=True, y=True)
        
        # Link X axis of row plot to the bottom image view
        if self._image_views[self.N_PLANES - 1]:
            self._row_plot.setXLink(self._image_views[self.N_PLANES - 1].getViewBox())
        
        self._glw.addItem(self._row_plot, row=self.N_PLANES, col=0)
        
        # Add vertical cursor to row plot
        self._row_v_cursor = pg.InfiniteLine(movable=False, angle=90, pen='r')
        self._row_plot.addItem(self._row_v_cursor)
        
        # Set row height ratio for the row plot
        self._glw.getRow(self.N_PLANES).setHeight(total_channels / 5)
        
        # Link X axes of all image views
        for i in range(self.N_PLANES):
            if self._image_views[i] and i > 0:
                self._image_views[i].getView().setXLink(self._image_views[0].getViewBox())
                
        # Add a placeholder item in the bottom right cell (N_PLANES, 1)
        self._glw.addItem(pg.PlotItem(), row=self.N_PLANES, col=1)


    def _set_cmap(self, name: str):
        """Callback to change the colormap."""
        self._current_cmap_name = name
        if self._current_frame:
            self._update_plots(self._current_frame)

    def _toggle_median_subtraction(self, state: int):
        """Callback to toggle median subtraction."""
        self._median_subtraction_active = (state == QtCore.Qt.Checked)
        
        if self._current_frame:
            self._update_plots(self._current_frame)

    def _get_processed_data(self, frame: Frame) -> np.ndarray:
        """Applies active data transformations to the frame data."""
        
        # Cast data to float before processing
        data = frame.frame.astype(np.float32)
        
        if self._median_subtraction_active:
            # Calculate median for each row (channel)
            row_medians = np.median(data, axis=1, keepdims=True)
            # Subtract median from each row
            data -= row_medians
            
        return data

    def _update_plots(self, frame: Frame):
        """Updates all plots based on the current frame data."""
        
        data = self._get_processed_data(frame)
        N_channels, N_ticks = data.shape
        
        plane_sizes = frame.plane_sizes()
        self._plane_sizes = plane_sizes
        self._plane_offsets = [0] + list(np.cumsum(self._plane_sizes[:-1]))
        
        is_initial_setup = self._image_views[0] is None
        
        if is_initial_setup:
            self._setup_graphics_layout(plane_sizes)
            # Set initial selection to center
            self._selected_global_row = plane_sizes[0] // 2
            self._selected_col = N_ticks // 2

        self.setWindowTitle(f"Frame {frame.event_number} ({frame.detector()}) - Teepeesee Trio Display (PyQtGraph)")
        
        # Determine colormap lookup
        if self._current_cmap_name == "seismic":
            # Use 'bipolar' for symmetric color scale around zero
            cmap = pg.colormap.get('bipolar')
        elif self._current_cmap_name == "rainbow":
            cmap = pg.colormap.get('hsv')
        else: # viridis or default
            cmap = pg.colormap.get('viridis')

        
        # 1. Update Image Views
        for i in range(self.N_PLANES):
            if self._plane_sizes[i] == 0:
                continue

            imv = self._image_views[i]
            if imv is None: continue

            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data = data[start_ch:end_ch, :]
            plane_size = self._plane_sizes[i]
            
            # Determine color limits based on processing state
            if self._median_subtraction_active:
                # Symmetric limits around zero
                max_abs = np.max(np.abs(data))
                vmin = -max_abs
                vmax = max_abs
            else:
                # Standard min/max limits
                vmin = data.min()
                vmax = data.max()

            # Flip data vertically (N_ch, N_t) -> to ensure row 0 (Channel 0) 
            # is displayed at the bottom (Y=0 in the view box).
            plane_data_flipped = np.flipud(plane_data)
            
            imv.setImage(
                plane_data_flipped, 
                xvals=np.arange(N_ticks), 
                autoRange=False, 
                autoLevels=False, 
                autoHistogramRange=False,
                levels=(vmin, vmax)
            )
            
            # Apply colormap
            imv.setColorMap(cmap)
            
            # Set view limits: Y range should be (0, plane_size)
            if is_initial_setup:
                imv.getView().setRange(xRange=(0, N_ticks), yRange=(0, plane_size))
                
            # Update levels
            imv.setLevels(vmin, vmax)
                
        # 2. Update 1D Plots and Cursors
        self._update_1d_plots(data, N_channels, N_ticks, is_initial_setup)
        
    def _on_image_click(self, event, clicked_ax_index: int):
        """Handles mouse clicks on any image plot to update 1D plots."""
        # Check if the click was a left button press
        if self._current_frame is None or not event.button() == QtCore.Qt.LeftButton:
            return
        
        # Get position in the ImageItem's local coordinates (data indices)
        # This position corresponds to the index in the array passed to setImage.
        local_pos = event.pos()
        
        x_data = local_pos.x()
        y_data = local_pos.y()
        
        if x_data is None or y_data is None:
            return

        data = self._current_frame.frame
        N_channels, N_ticks = data.shape
        
        plane_size = self._plane_sizes[clicked_ax_index]
        
        # 1. Calculate local row index (within the clicked plane)
        
        # Calculate index in the flipped array (0 at top, plane_size-1 at bottom)
        local_row_flipped = int(np.clip(round(y_data), 0, plane_size - 1))
        
        # Map back to original channel index (0 at bottom, plane_size-1 at top)
        local_row = plane_size - 1 - local_row_flipped
        
        # 2. Calculate global row index
        plane_offset = self._plane_offsets[clicked_ax_index]
        new_global_row = plane_offset + local_row
        
        # 3. Calculate column index (Ticks)
        new_col = int(np.clip(round(x_data), 0, N_ticks - 1))
        
        if new_global_row != self._selected_global_row or new_col != self._selected_col:
            self._selected_global_row = new_global_row
            self._selected_col = new_col
            
            processed_data = self._get_processed_data(self._current_frame)
            self._update_1d_plots(processed_data, N_channels, N_ticks, is_initial_setup=False)


    def _update_1d_plots(self, data: np.ndarray, N_channels: int, N_ticks: int, is_initial_setup: bool):
        """Updates the row/column plots and cursor lines."""
        
        # Ensure selected indices are within bounds
        global_row = max(0, min(self._selected_global_row, N_channels - 1))
        col = max(0, min(self._selected_col, N_ticks - 1))
        
        # --- Row Plot (Time profile for selected channel) ---
        if self._row_plot:
            if self._row_line_handle is None:
                # Plot data[global_row, :] vs Ticks (0 to N_ticks)
                self._row_line_handle = self._row_plot.plot(data[global_row, :], pen='b', stepMode=True, fillLevel=None)
                self._row_plot.setXRange(0, N_ticks)
            else:
                self._row_line_handle.setData(data[global_row, :])
            
            self._row_plot.setTitle(f"Global Channel {global_row} Profile")
            
            # Update vertical cursor position
            if self._row_v_cursor:
                self._row_v_cursor.setPos(col)
        
        # --- Column Plots (Channel profiles for selected tick) ---
        
        for i in range(self.N_PLANES):
            if self._plane_sizes[i] == 0:
                continue

            col_plot = self._col_plots[i]
            if col_plot is None: continue
            
            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data_col = data[start_ch:end_ch, col]
            plane_size = self._plane_sizes[i]
            
            # Local row index within this plane
            local_row = global_row - start_ch
            
            # Y data (channel indices) runs from 0 to plane_size - 1
            y_channels = np.arange(plane_size)
            
            # Plot (Amplitude, Channel Index)
            
            if self._col_line_handles[i] is None:
                # Initial plot setup
                self._col_line_handles[i] = col_plot.plot(plane_data_col, y_channels, pen=pg.mkPen(color=(0, 0, 0), width=1), stepMode=True, fillLevel=None)
                col_plot.setYRange(0, plane_size)
            else:
                # Update X data (amplitude)
                self._col_line_handles[i].setData(plane_data_col, y_channels)
            
            col_plot.setTitle(f"Plane {i} Tick {col}")
            
            # Update horizontal cursor position
            h_cursor = self._h_cursors[i]
            if h_cursor:
                if start_ch <= global_row < end_ch:
                    h_cursor.setPos(local_row)
                    h_cursor.show()
                else:
                    h_cursor.hide() # Hide cursor if selected channel is outside this plane

            # Update vertical cursor position on image view
            v_cursor = self._v_cursors[i]
            if v_cursor:
                v_cursor.setPos(col)
                
    def show(self, frame: Frame):
        """
        Displays the data contained in the Frame instance.
        """
        self._current_frame = frame
        
        # Setup graphics layout if not done, and update plots
        self._update_plots(frame)
        
        # Ensure the widget is shown
        self.show()
