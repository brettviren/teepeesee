from qtpy import QtCore as qc
from qtpy import QtWidgets as qw
import pyqtgraph as pg
import numpy as np

class FrameTime(pg.PlotWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.curves = []  # List of curves for multi-source display

    def update_trace(self, data_slice):
        """Update with single data slice (legacy mode)."""
        # Clear existing curves and create single yellow curve
        self.clear()
        self.curves = [self.plot(pen='y', stepMode="center")]
        bins = np.arange(len(data_slice) + 1)
        self.curves[0].setData(x=bins, y=data_slice)

    def update_multi_trace(self, data_slices):
        """Update with multiple data slices (RGB Multi mode).

        data_slices: list of numpy arrays, one per source
        """
        colors = ['r', 'g', 'b']  # Red, Green, Blue
        self.clear()
        self.curves = []

        for i, data_slice in enumerate(data_slices[:3]):  # Max 3 sources
            if data_slice is not None:
                color = colors[i] if len(data_slices) > 1 else 'r'  # Single source uses red
                curve = self.plot(pen=color, stepMode="center")
                bins = np.arange(len(data_slice) + 1)
                curve.setData(x=bins, y=data_slice)
                self.curves.append(curve)

    def clear(self):
        """Clear all plots."""
        for item in self.items():
            self.removeItem(item)
        self.curves = []


class FrameChan(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(100)
        self.curves = []  # List of curves for multi-source display

    def update_trace(self, data_slice):
        """Update with single data slice (legacy mode)."""
        # Clear existing curves and create single cyan curve
        self.clear()
        self.curves = [self.plot(pen='c', stepMode="center")]
        bins = np.arange(len(data_slice)-1)
        self.curves[0].setData(x=data_slice, y=bins)

    def update_multi_trace(self, data_slices):
        """Update with multiple data slices (RGB Multi mode).

        data_slices: list of numpy arrays, one per source
        """
        colors = ['r', 'g', 'b']  # Red, Green, Blue
        self.clear()
        self.curves = []

        for i, data_slice in enumerate(data_slices[:3]):  # Max 3 sources
            if data_slice is not None:
                color = colors[i] if len(data_slices) > 1 else 'r'  # Single source uses red
                curve = self.plot(pen=color, stepMode="center")
                bins = np.arange(len(data_slice)-1)
                curve.setData(x=data_slice, y=bins)
                self.curves.append(curve)

    def clear(self):
        """Clear all plots."""
        for item in self.items():
            self.removeItem(item)
        self.curves = []


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
    selectionChanged = qc.Signal(int, int)
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
        # Set initial range to reasonable values instead of pyqtgraph's default (-1, 1)
        # This will be overridden by reset_to_default_view() once data is loaded
        self.getViewBox().setRange(xRange=(0, 1000), yRange=(0, 1000), padding=0)

    def toggle_grid(self, state):
        self.showGrid(x=state, y=state, alpha=0.3)

    def set_lines(self, x, y):
        self.v_line.setValue(x)
        self.h_line.setValue(y)
        self.getViewBox().update()

    def emit_selection(self):
        self.selectionChanged.emit(int(self.v_line.value()),
                                   int(self.h_line.value()))

    def handle_click(self, event):
        if event.button() == qc.Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if self.image_item.sceneBoundingRect().contains(pos):
                pt = self.image_item.mapFromScene(pos)
                self.set_lines(pt.x(), pt.y())
                self.emit_selection()

class FrameDisplay(qw.QWidget):
    userSelectionChanged = qc.Signal(int, int)
    def __init__(self):
        super().__init__()
        self.original_data = None
        self.baseline_data = None
        self.multi_source_data = []  # List of data arrays for RGB multi mode
        self.multi_baseline_data = []  # List of baseline arrays for RGB multi mode
        self._rgb_multi_mode = False
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
        self.f_time.setXLink(self.f_image)
        self.f_chan.setYLink(self.f_image)
        self.f_image.selectionChanged.connect(self._on_internal_change)
        self.f_image.getViewBox().sigRangeChanged.connect(self._on_range_changed)
        self.f_image.getViewBox().sigRangeChanged.connect(self.update_hist_region)

    def enterEvent(self, event):
        "Automatically grab focus when mouse enters, enabling arrow key nudging."
        self.setFocus()
        super().enterEvent(event)

    def keyPressEvent(self, event):
        "Handle arrow key nudging."
        step = 1
        if event.modifiers() & qc.Qt.KeyboardModifier.ShiftModifier:
            step = 10
            
        cur_x = self.f_image.v_line.value()
        cur_y = self.f_image.h_line.value()

        if event.key() == qc.Qt.Key.Key_Left:
            self.update_v_line_from_user(cur_x - step)
        elif event.key() == qc.Qt.Key.Key_Right:
            self.update_v_line_from_user(cur_x + step)
        elif event.key() == qc.Qt.Key.Key_Down:
            self.update_h_line_from_user(cur_y - step)
        elif event.key() == qc.Qt.Key.Key_Up:
            self.update_h_line_from_user(cur_y + step)
        else:
            super().keyPressEvent(event)

    def update_v_line_from_user(self, x):
        self.f_image.v_line.setValue(x)
        self.f_image.emit_selection()

    def update_h_line_from_user(self, y):
        self.f_image.h_line.setValue(y)
        self.f_image.emit_selection()

    @qc.Slot(np.ndarray)
    def updateData(self, samples=None, channels=None, tickinfo=None):
        self.current_channels = channels
        self.current_tickinfo = tickinfo
        self.original_data = samples
        self.baseline_data = samples - np.median(samples, axis=1, keepdims=True)
        self._apply_current_state()

    def set_rgb_multi_mode(self, enabled):
        """Enable or disable RGB multi mode."""
        self._rgb_multi_mode = enabled
        self._apply_current_state()

    def updateMultiData(self, data_list):
        """Update with data from multiple sources for RGB multi mode.

        data_list: list of dicts with 'samples', 'channels', 'tickinfo' keys
        """
        self.multi_source_data = []
        self.multi_baseline_data = []

        for data_dict in data_list[:3]:  # Max 3 sources
            samples = data_dict.get('samples')
            if samples is not None:
                self.multi_source_data.append(samples)
                baseline = samples - np.median(samples, axis=1, keepdims=True)
                self.multi_baseline_data.append(baseline)

        # Use first source's metadata for display
        if data_list:
            self.current_channels = data_list[0].get('channels')
            self.current_tickinfo = data_list[0].get('tickinfo')

        self._apply_current_state()

    def clear(self):
        """Clear the display, showing no data."""
        self.original_data = None
        self.baseline_data = None
        self.multi_source_data = []
        self.multi_baseline_data = []
        self.current_channels = None
        self.current_tickinfo = None
        self.f_image.image_item.clear()
        self.f_time.clear()
        self.f_chan.clear()

    def _create_rgb_composite(self):
        """Create RGB composite image from multiple sources."""
        if not self.multi_source_data:
            return None

        # Get data list (rebaseline if active)
        data_list = self.multi_baseline_data if self._rebaseline_active else self.multi_source_data

        # Get the shape from first source
        h, w = data_list[0].shape

        # Create RGB image (height, width, 3)
        rgb_image = np.zeros((h, w, 3), dtype=np.float32)

        # Assign sources to R, G, B channels
        # Single source: Red only
        # Two sources: Red and Green
        # Three+ sources: Red, Green, Blue
        for i, data in enumerate(data_list[:3]):
            # Normalize to [0, 1]
            data_min, data_max = np.nanmin(data), np.nanmax(data)
            if data_max > data_min:
                normalized = (data - data_min) / (data_max - data_min)
            else:
                normalized = np.zeros_like(data)

            rgb_image[:, :, i] = normalized

        return rgb_image

    def _apply_current_state(self):
        if self._rgb_multi_mode and self.multi_source_data:
            # RGB multi mode
            rgb_image = self._create_rgb_composite()
            if rgb_image is not None:
                self.f_image.image_item.setImage(rgb_image, autoLevels=False)
                self.f_image.emit_selection()
                # Histogram doesn't apply in RGB mode
        elif self.original_data is not None:
            # Normal single-source mode
            data = self.baseline_data if self._rebaseline_active else self.original_data
            self.f_image.image_item.setImage(data, autoLevels=False)
            self.f_image.emit_selection()
            self.update_hist_region()

    def auto_contrast(self):
        # Skip auto contrast in RGB Multi mode (image is already normalized)
        if self._rgb_multi_mode:
            return

        data = self.f_image.image_item.image
        if data is None:
            return

        # Skip if data is 3D (RGB image)
        if len(data.shape) == 3:
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
        # Skip histogram update in RGB Multi mode
        if self._rgb_multi_mode:
            return

        data = self.f_image.image_item.image
        if data is None:
            return

        # Skip if data is 3D (RGB image)
        if len(data.shape) == 3:
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
            if self._rgb_multi_mode and self.multi_source_data:
                # RGB multi mode: extract slices from individual sources
                data_list = self.multi_baseline_data if self._rebaseline_active else self.multi_source_data
                h, w = data_list[0].shape
                c, r = int(np.clip(col, 0, w - 1)), int(np.clip(row, 0, h - 1))

                # Update info box with first source's value
                self.f_image.info_box.update_info(c, r, data_list[0][r, c],
                                                  getattr(self, "current_tickinfo", None))

                # Extract slices from all sources for 1D plots
                time_slices = [d[r, :] for d in data_list]
                chan_slices = [d[:, c] for d in data_list]

                self.f_time.update_multi_trace(time_slices)
                self.f_chan.update_multi_trace(chan_slices)
            else:
                # Normal single-source mode
                h, w = data.shape
                c, r = int(np.clip(col, 0, w - 1)), int(np.clip(row, 0, h - 1))
                self.f_image.info_box.update_info(c, r, data[r, c],
                                                  getattr(self, "current_tickinfo", None))
                self.f_time.update_trace(data[r, :])
                self.f_chan.update_trace(data[:, c])
        if not self._is_syncing:
            self.userSelectionChanged.emit(col, row)

    def set_crosshair(self, x, y):
        self.f_image.set_lines(x, y)
        self._on_internal_change(x, y)


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
