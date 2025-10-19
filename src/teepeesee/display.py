import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import List, Optional, Tuple

# Assuming Frame is importable from teepeesee.io
from .io import Frame

class Display:
    """
    Provides an interactive display for Frame data using Matplotlib.
    """
    def __init__(self):
        self._fig: Optional[Figure] = None
        self._ax_img: Optional[Axes] = None
        self._ax_row: Optional[Axes] = None
        self._ax_col: Optional[Axes] = None
        
        self._img_handle = None
        self._row_line_handle = None
        self._col_line_handle = None
        self._h_cursor_handle = None
        self._v_cursor_handle = None
        
        self._current_frame: Optional[Frame] = None
        self._selected_row: int = 0
        self._selected_col: int = 0

    def _setup_figure(self):
        """Initializes the figure and axes layout."""
        if self._fig is not None:
            # Figure already exists, reuse it
            return

        # Create a figure with a complex layout:
        # Top left: 2D image (ax_img)
        # Bottom left: 1D row plot (ax_row)
        # Top right: 1D column plot (ax_col)
        
        self._fig = plt.figure(figsize=(10, 8))
        
        # Define grid structure: 2 rows, 2 columns
        gs = self._fig.add_gridspec(2, 2, width_ratios=[3, 1], height_ratios=[3, 1], 
                                    hspace=0.3, wspace=0.3)

        self._ax_img = self._fig.add_subplot(gs[0, 0])
        self._ax_row = self._fig.add_subplot(gs[1, 0], sharex=self._ax_img)
        self._ax_col = self._fig.add_subplot(gs[0, 1], sharey=self._ax_img)
        
        # Hide tick labels for shared axes to clean up display
        self._ax_img.tick_params(axis='x', labelbottom=False)
        self._ax_col.tick_params(axis='y', labelleft=False)
        
        # Set up labels
        self._ax_img.set_title("Frame Data")
        self._ax_img.set_xlabel("Ticks")
        self._ax_img.set_ylabel("Channels")
        
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        
        self._ax_col.set_xlabel("Amplitude")
        self._ax_col.set_ylabel("Channels")
        
        # Connect click event handler
        self._fig.canvas.mpl_connect('button_press_event', self._on_click)
        
        # Ensure the column plot is oriented correctly (channels on Y axis)
        self._ax_col.invert_xaxis() # Plot amplitude left-to-right, channels bottom-to-top

    def _draw_plane_boundaries(self, plane_sizes: List[int]):
        """Draws horizontal lines indicating plane boundaries on the image plot."""
        if not self._ax_img:
            return

        # Clear previous boundary lines
        for line in self._ax_img.lines:
            if line.get_linestyle() == '--':
                line.remove()

        current_channel = 0
        # We only need N-1 lines for N planes
        for size in plane_sizes[:-1]:
            current_channel += size
            # Draw a dashed horizontal line
            self._ax_img.axhline(current_channel, color='w', linestyle='--', linewidth=1, alpha=0.8)
            
        self._ax_img.figure.canvas.draw_idle()

    def _update_plots(self, frame: Frame):
        """Updates the image and 1D plots based on the current frame data."""
        data = frame.frame
        N_channels, N_ticks = data.shape
        
        # 1. Update Image Plot (ax_img)
        if self._img_handle is None:
            # Initial draw: use imshow
            self._img_handle = self._ax_img.imshow(
                data, 
                aspect='auto', 
                origin='lower', 
                interpolation='nearest',
                cmap='viridis'
            )
            self._ax_img.set_xlim(0, N_ticks)
            self._ax_img.set_ylim(0, N_channels)
            
            # Set initial selection to center
            self._selected_row = N_channels // 2
            self._selected_col = N_ticks // 2
            
        else:
            # Subsequent draw: update data
            self._img_handle.set_data(data)
            # Recalculate color limits if data range changes significantly
            self._img_handle.set_clim(data.min(), data.max())
            
        # Update title with detector info
        self._ax_img.set_title(f"Frame {frame.event_number} ({frame.detector()})")

        # Draw plane boundaries
        self._draw_plane_boundaries(frame.plane_sizes())
        
        # 2. Update 1D Plots and Cursors
        self._update_1d_plots(data, N_channels, N_ticks)
        
        self._fig.canvas.draw_idle()

    def _update_1d_plots(self, data: np.ndarray, N_channels: int, N_ticks: int):
        """Updates the row/column plots and cursor lines."""
        
        # Ensure selected indices are within bounds
        row = min(self._selected_row, N_channels - 1)
        col = min(self._selected_col, N_ticks - 1)
        
        # --- Row Plot (Time profile for selected channel) ---
        self._ax_row.clear()
        self._ax_row.set_title(f"Channel {row} Profile")
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        
        self._row_line_handle, = self._ax_row.plot(data[row, :], color='C0')
        self._ax_row.axvline(col, color='r', linestyle=':', linewidth=1)
        self._ax_row.set_xlim(0, N_ticks)
        self._ax_row.autoscale_view(tight=True, scalex=False, scaley=True)
        
        # --- Column Plot (Channel profile for selected tick) ---
        self._ax_col.clear()
        self._ax_col.set_title(f"Tick {col} Profile")
        self._ax_col.set_xlabel("Amplitude")
        self._ax_col.set_ylabel("Channels")
        
        # Plot data[0:N_channels, col] against channel index (0 to N_channels)
        # We plot (Amplitude, Channel Index)
        self._col_line_handle, = self._ax_col.plot(data[:, col], np.arange(N_channels), color='C1')
        self._ax_col.axhline(row, color='r', linestyle=':', linewidth=1)
        self._ax_col.set_ylim(0, N_channels)
        self._ax_col.autoscale_view(tight=True, scalex=True, scaley=False)
        
        # Invert X axis for column plot to match typical amplitude display
        self._ax_col.invert_xaxis() 
        
        # --- Cursors on Image Plot ---
        if self._h_cursor_handle:
            self._h_cursor_handle.remove()
        if self._v_cursor_handle:
            self._v_cursor_handle.remove()
            
        # Horizontal cursor (Channel selection)
        self._h_cursor_handle = self._ax_img.axhline(row, color='r', linestyle='-', linewidth=1)
        # Vertical cursor (Tick selection)
        self._v_cursor_handle = self._ax_img.axvline(col, color='r', linestyle='-', linewidth=1)
        
        # Ensure shared axes limits are respected
        self._ax_row.set_xlim(self._ax_img.get_xlim())
        self._ax_col.set_ylim(self._ax_img.get_ylim())
        
        # Redraw required for clear() usage
        self._fig.canvas.draw_idle()


    def _on_click(self, event):
        """Handles mouse clicks on the image plot to update 1D plots."""
        if event.inaxes != self._ax_img or self._current_frame is None:
            return

        x_data = event.xdata
        y_data = event.ydata
        
        if x_data is None or y_data is None:
            return

        data = self._current_frame.frame
        N_channels, N_ticks = data.shape
        
        # Map click coordinates to integer indices
        # Y-axis (channels) is plotted 'lower' (0 at bottom)
        new_row = int(round(y_data))
        new_col = int(round(x_data))
        
        # Clamp indices
        new_row = max(0, min(new_row, N_channels - 1))
        new_col = max(0, min(new_col, N_ticks - 1))
        
        if new_row != self._selected_row or new_col != self._selected_col:
            self._selected_row = new_row
            self._selected_col = new_col
            self._update_1d_plots(data, N_channels, N_ticks)

    def show(self, frame: Frame):
        """
        Displays the data contained in the Frame instance.
        Reuses the existing figure if available.
        """
        self._current_frame = frame
        
        if self._fig is None:
            self._setup_figure()
            
        self._update_plots(frame)
        
        # Ensure the figure is shown interactively
        plt.show(block=False)

