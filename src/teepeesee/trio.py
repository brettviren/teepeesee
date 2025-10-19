import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import List, Optional, Tuple, Dict

# Assuming Frame is importable from teepeesee.io
from .io import Frame

class TrioDisplay:
    """
    Provides an interactive display for Frame data, splitting the visualization
    into three separate channel planes for independent scaling and zooming.
    """
    N_PLANES = 3

    def __init__(self):
        self._fig: Optional[Figure] = None
        
        # Axes storage: [ax_img_0, ax_img_1, ax_img_2]
        self._ax_imgs: List[Optional[Axes]] = [None] * self.N_PLANES
        # Axes storage: [ax_col_0, ax_col_1, ax_col_2]
        self._ax_cols: List[Optional[Axes]] = [None] * self.N_PLANES
        # Single row profile axis
        self._ax_row: Optional[Axes] = None
        
        # Handles for image data
        self._img_handles = [None] * self.N_PLANES
        
        self._current_frame: Optional[Frame] = None
        self._plane_sizes: List[int] = []
        self._plane_offsets: List[int] = []
        
        # Global indices for selected point
        self._selected_global_row: int = 0
        self._selected_col: int = 0

    def _setup_figure(self, plane_sizes: List[int]):
        """Initializes the figure and axes layout with proportional heights."""
        if self._fig is not None:
            # Figure already exists, reuse it
            return

        self._fig = plt.figure(figsize=(12, 10))
        
        # Height ratios: [Plane 0 size, Plane 1 size, Plane 2 size, Row Plot size]
        total_channels = sum(plane_sizes)
        
        # Row plot height is fixed relative to the total channel height (e.g., 20%)
        height_ratios = [size for size in plane_sizes] + [total_channels / 5] 
        
        # Define grid structure: 4 rows (3 planes + 1 row plot), 2 columns (Image + Column Profile)
        gs = self._fig.add_gridspec(
            self.N_PLANES + 1, 
            2, 
            width_ratios=[3, 1], 
            height_ratios=height_ratios,
            hspace=0.05, # Minimal vertical space between plane images
            wspace=0.3
        )

        # 1. Setup Image and Column Axes (Planes 0, 1, 2)
        for i in range(self.N_PLANES):
            # Image Axis (Left column, rows 0, 1, 2)
            ax_img = self._fig.add_subplot(gs[i, 0])
            self._ax_imgs[i] = ax_img
            
            # Column Profile Axis (Right column, rows 0, 1, 2)
            ax_col = self._fig.add_subplot(gs[i, 1], sharey=ax_img)
            self._ax_cols[i] = ax_col
            
            # Synchronization and cleanup
            ax_col.tick_params(axis='y', labelleft=False)
            ax_col.invert_xaxis() # Amplitude left-to-right
            
            # Hide X ticks for upper images
            if i < self.N_PLANES - 1:
                ax_img.tick_params(axis='x', labelbottom=False)
            
            ax_img.set_ylabel(f"Plane {i} Channels")
            ax_col.set_xlabel("Amplitude")

        # 2. Setup Row Axis (Bottom row, spans 2 columns)
        self._ax_row = self._fig.add_subplot(gs[self.N_PLANES, :])
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        
        # Share X axis between all image plots and the row plot
        for i in range(self.N_PLANES):
            self._ax_imgs[i].sharex(self._ax_row)

        # Connect click event handler
        self._fig.canvas.mpl_connect('button_press_event', self._on_click)
        
        self._fig.tight_layout()
        # Adjust layout to prevent row plot from overlapping shared X labels
        self._fig.subplots_adjust(bottom=0.1, top=0.95)


    def _update_plots(self, frame: Frame):
        """Updates all plots based on the current frame data."""
        data = frame.frame
        N_channels, N_ticks = data.shape
        
        self._plane_sizes = frame.plane_sizes()
        
        # Calculate offsets: [0, size0, size0+size1]
        self._plane_offsets = [0] + list(np.cumsum(self._plane_sizes[:-1]))
        
        # If figure is not set up, set it up now with correct proportional sizes
        if self._fig is None:
            self._setup_figure(self._plane_sizes)
            
            # Set initial selection to center of the first plane
            self._selected_global_row = self._plane_sizes[0] // 2
            self._selected_col = N_ticks // 2

        # Update title
        self._fig.suptitle(f"Frame {frame.event_number} ({frame.detector()})", fontsize=14)

        # 1. Update Image Plots (Planes)
        global_min = data.min()
        global_max = data.max()
        
        for i in range(self.N_PLANES):
            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data = data[start_ch:end_ch, :]
            
            ax_img = self._ax_imgs[i]
            
            if self._img_handles[i] is None:
                # Initial draw
                self._img_handles[i] = ax_img.imshow(
                    plane_data, 
                    aspect='auto', 
                    origin='lower', 
                    interpolation='nearest',
                    cmap='viridis'
                )
                # Set Y limits based on local channel index (0 to plane_size)
                ax_img.set_ylim(0, self._plane_sizes[i])
                
            else:
                # Subsequent draw: update data
                self._img_handles[i].set_data(plane_data)
                
            # Ensure color limits are consistent across all planes
            self._img_handles[i].set_clim(global_min, global_max)
            
            # Set X limits (shared)
            ax_img.set_xlim(0, N_ticks)
            
            # Update column axis limits
            self._ax_cols[i].set_ylim(0, self._plane_sizes[i])


        # 2. Update 1D Plots and Cursors
        self._update_1d_plots(data, N_channels, N_ticks)
        
        self._fig.canvas.draw_idle()

    def _update_1d_plots(self, data: np.ndarray, N_channels: int, N_ticks: int):
        """Updates the row/column plots and cursor lines."""
        
        # Ensure selected indices are within bounds
        global_row = max(0, min(self._selected_global_row, N_channels - 1))
        col = max(0, min(self._selected_col, N_ticks - 1))
        
        # --- Row Plot (Time profile for selected channel) ---
        self._ax_row.clear()
        self._ax_row.set_title(f"Global Channel {global_row} Profile")
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        
        self._ax_row.plot(data[global_row, :], color='C0')
        self._ax_row.axvline(col, color='r', linestyle=':', linewidth=1)
        self._ax_row.set_xlim(0, N_ticks)
        self._ax_row.autoscale_view(tight=True, scalex=False, scaley=True)
        
        # --- Column Plots (Channel profiles for selected tick) ---
        
        # Clear previous cursors from image plots
        for ax_img in self._ax_imgs:
            # Remove all lines (cursors)
            ax_img.lines.clear()
            
        
        for i in range(self.N_PLANES):
            ax_col = self._ax_cols[i]
            ax_img = self._ax_imgs[i]
            
            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data_col = data[start_ch:end_ch, col]
            plane_size = self._plane_sizes[i]
            
            # Local row index within this plane
            local_row = global_row - start_ch
            
            ax_col.clear()
            ax_col.set_title(f"Plane {i} Tick {col}")
            ax_col.set_xlabel("Amplitude")
            
            # Plot data[0:plane_size, col] against local channel index (0 to plane_size)
            ax_col.plot(plane_data_col, np.arange(plane_size), color=f'C{i+1}')
            ax_col.set_ylim(0, plane_size)
            ax_col.autoscale_view(tight=True, scalex=True, scaley=False)
            ax_col.invert_xaxis() 
            
            # Draw horizontal cursor on column plot if the selected row is in this plane
            if start_ch <= global_row < end_ch:
                ax_col.axhline(local_row, color='r', linestyle=':', linewidth=1)
                
                # Draw horizontal cursor on image plot
                ax_img.axhline(local_row, color='r', linestyle='-', linewidth=1)
            
            # Draw vertical cursor on image plot (shared tick selection)
            ax_img.axvline(col, color='r', linestyle='-', linewidth=1)
            
            # Ensure Y label is present only on the leftmost plot
            if i == 0:
                ax_col.set_ylabel("Channels")
            else:
                ax_col.tick_params(axis='y', labelleft=False)
                
            # Ensure X label is present only on the bottom image plot
            if i == self.N_PLANES - 1:
                ax_img.set_xlabel("Ticks")
            else:
                ax_img.tick_params(axis='x', labelbottom=False)

        # Redraw required for clear() usage
        self._fig.canvas.draw_idle()


    def _on_click(self, event):
        """Handles mouse clicks on any image plot to update 1D plots."""
        if self._current_frame is None:
            return

        clicked_ax_index = -1
        for i, ax_img in enumerate(self._ax_imgs):
            if event.inaxes == ax_img:
                clicked_ax_index = i
                break
        
        if clicked_ax_index == -1:
            return # Clicked outside image axes

        x_data = event.xdata
        y_data = event.ydata
        
        if x_data is None or y_data is None:
            return

        data = self._current_frame.frame
        N_channels, N_ticks = data.shape
        
        # 1. Calculate local row index (within the clicked plane)
        local_row = int(round(y_data))
        
        # 2. Calculate global row index
        plane_offset = self._plane_offsets[clicked_ax_index]
        new_global_row = plane_offset + local_row
        
        # 3. Calculate column index
        new_col = int(round(x_data))
        
        # Clamp indices
        new_global_row = max(0, min(new_global_row, N_channels - 1))
        new_col = max(0, min(new_col, N_ticks - 1))
        
        if new_global_row != self._selected_global_row or new_col != self._selected_col:
            self._selected_global_row = new_global_row
            self._selected_col = new_col
            self._update_1d_plots(data, N_channels, N_ticks)

    def show(self, frame: Frame):
        """
        Displays the data contained in the Frame instance.
        Reuses the existing figure if available.
        """
        self._current_frame = frame
        
        # Setup figure and update plots
        self._update_plots(frame)
        
        # Ensure the figure is shown interactively
        plt.show(block=False)
