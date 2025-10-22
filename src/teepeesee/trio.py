import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.widgets import RadioButtons, CheckButtons
from matplotlib.colors import Normalize
from typing import List, Optional, Tuple, Dict

# Assuming Frame is importable from teepeesee.io
from .io import Frame

class TrioDisplay:
    """
    Provides an interactive display for Frame data, splitting the visualization
    into three separate channel planes for independent scaling and zooming.
    Includes GUI widgets for control and interactive colorbars.
    """
    N_PLANES = 3
    AVAILABLE_CMAPS = ["viridis", "seismic", "rainbow"]

    def __init__(self):
        self._fig: Optional[Figure] = None
        
        # Axes storage
        self._ax_imgs: List[Optional[Axes]] = [None] * self.N_PLANES
        self._ax_cols: List[Optional[Axes]] = [None] * self.N_PLANES
        self._ax_cbars: List[Optional[Axes]] = [None] * self.N_PLANES # New axes for colorbars
        self._ax_row: Optional[Axes] = None
        
        # Widget axes storage
        self._ax_cmap: Optional[Axes] = None
        self._ax_median: Optional[Axes] = None
        
        # Widget storage
        self._cmap_radio: Optional[RadioButtons] = None
        self._median_check: Optional[CheckButtons] = None
        
        # Handles for image data and colorbars
        self._img_handles = [None] * self.N_PLANES
        self._cbar_handles = [None] * self.N_PLANES
        
        # Handles for 1D plots (Strategy 1 optimization)
        self._row_line_handle = None
        self._col_line_handles = [None] * self.N_PLANES
        
        self._current_frame: Optional[Frame] = None
        self._plane_sizes: List[int] = []
        self._plane_offsets: List[int] = []
        
        # State variables for controls
        self._current_cmap: str = self.AVAILABLE_CMAPS[0]
        self._median_subtraction_active: bool = False
        
        # Global indices for selected point
        self._selected_global_row: int = 0
        self._selected_col: int = 0

    def _setup_figure(self, plane_sizes: List[int]):
        """Initializes the figure and axes layout with proportional heights and controls."""
        if self._fig is not None:
            # Figure already exists, reuse it
            return

        self._fig = plt.figure(figsize=(14, 10)) # Increased width for colorbars
        
        # Height ratios: [Plane 0 size, Plane 1 size, Plane 2 size, Row Plot size]
        total_channels = sum(plane_sizes)
        height_ratios = [size for size in plane_sizes] + [total_channels / 5] 
        
        # Define grid structure: 4 rows, 3 columns (Image | Colorbar | Column Profile)
        # Width ratios: [Image (3), Colorbar (0.2), Column Profile (1)]
        gs = self._fig.add_gridspec(
            self.N_PLANES + 1, 
            3, 
            width_ratios=[3, 0.2, 1], 
            height_ratios=height_ratios,
            hspace=0.05, # Minimal vertical space between plane images
            wspace=0.1 # Reduced wspace to fit colorbars
        )

        # 1. Setup Image, Colorbar, and Column Axes (Planes 0, 1, 2)
        for i in range(self.N_PLANES):
            # Image Axis (Column 0)
            ax_img = self._fig.add_subplot(gs[i, 0])
            self._ax_imgs[i] = ax_img
            
            # Colorbar Axis (Column 1)
            ax_cbar = self._fig.add_subplot(gs[i, 1])
            self._ax_cbars[i] = ax_cbar
            
            # Column Profile Axis (Column 2)
            ax_col = self._fig.add_subplot(gs[i, 2], sharey=ax_img)
            self._ax_cols[i] = ax_col
            
            # Synchronization and cleanup
            ax_col.tick_params(axis='y', labelleft=False)
            # ax_col.invert_xaxis() # Amplitude left-to-right
            
            # Hide X ticks for upper images
            if i < self.N_PLANES - 1:
                ax_img.tick_params(axis='x', labelbottom=False)
            
            ax_img.set_ylabel(f"Plane {i} Channels")
            ax_col.set_xlabel("Amplitude")
            
            # Hide ticks/labels on colorbar axis initially
            ax_cbar.tick_params(labelleft=False, labelright=True, left=False, right=True)
            
            # Connect custom colorbar interaction handlers
            ax_cbar.figure.canvas.mpl_connect('scroll_event', self._on_cbar_scroll)
            ax_cbar.figure.canvas.mpl_connect('button_press_event', self._on_cbar_click)


        # 2. Setup Row Axis (Bottom row, spans ONLY the first column)
        self._ax_row = self._fig.add_subplot(gs[self.N_PLANES, 0])
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        
        # Share X axis between all image plots and the row plot
        for i in range(self.N_PLANES):
            self._ax_imgs[i].sharex(self._ax_row)

        # 3. Setup Control Widgets (Bottom right corner, using grid cell gs[3, 2])
        
        # Create a temporary axis for controls in the bottom right cell (gs[3, 2])
        ax_controls_placeholder = self._fig.add_subplot(gs[self.N_PLANES, 2])
        
        # Run tight_layout once to calculate positions accurately
        self._fig.tight_layout()
        
        # Get the position of the target grid cell
        control_pos = ax_controls_placeholder.get_position()
        ax_controls_placeholder.remove() # Remove placeholder axis
        
        # Colormap Radio Buttons (Top part of control cell)
        # [left, bottom, width, height] relative to figure
        self._ax_cmap = self._fig.add_axes([
            control_pos.x0, 
            control_pos.y0 + control_pos.height * 0.3, 
            control_pos.width, 
            control_pos.height * 0.6
        ]) 
        self._ax_cmap.set_title("Colormap", fontsize=10)
        self._ax_cmap.tick_params(labelbottom=False, labelleft=False, bottom=False, left=False)
        
        self._cmap_radio = RadioButtons(self._ax_cmap, self.AVAILABLE_CMAPS, active=0)
        self._cmap_radio.on_clicked(self._set_cmap)
        
        # Median Subtraction Check Button (Bottom part of control cell)
        self._ax_median = self._fig.add_axes([
            control_pos.x0, 
            control_pos.y0, 
            control_pos.width, 
            control_pos.height * 0.2
        ])
        self._ax_median.tick_params(labelbottom=False, labelleft=False, bottom=False, left=False)
        
        self._median_check = CheckButtons(self._ax_median, ['Subtract Median'], [False])
        self._median_check.on_clicked(self._toggle_median_subtraction)
        
        # Connect click event handler for cursor updates
        self._fig.canvas.mpl_connect('button_press_event', self._on_click)
        
        # Final adjustment to ensure widgets are visible and aligned
        self._fig.subplots_adjust(bottom=0.1, top=0.95, right=0.95, left=0.05)
        
    def _set_cmap(self, label: str):
        """Callback to change the colormap."""
        self._current_cmap = label
        if self._current_frame:
            self._update_plots(self._current_frame)

    def _toggle_median_subtraction(self, label: str):
        """Callback to toggle median subtraction."""
        self._median_subtraction_active = self._median_check.get_status()[0]
        
        if self._current_frame:
            self._update_plots(self._current_frame)

    def _get_processed_data(self, frame: Frame) -> np.ndarray:
        """Applies active data transformations to the frame data."""
        
        # Cast data to float before processing to avoid integer overflow/casting errors
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
        
        self._plane_sizes = frame.plane_sizes()
        self._plane_offsets = [0] + list(np.cumsum(self._plane_sizes[:-1]))
        
        is_initial_setup = self._fig is None
        
        if is_initial_setup:
            self._setup_figure(self._plane_sizes)
            self._selected_global_row = self._plane_sizes[0] // 2
            self._selected_col = N_ticks // 2

        self._fig.suptitle(f"Frame {frame.event_number} ({frame.detector()})", fontsize=14)

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
        
        
        for i in range(self.N_PLANES):
            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data = data[start_ch:end_ch, :]
            
            ax_img = self._ax_imgs[i]
            ax_col = self._ax_cols[i]
            ax_cbar = self._ax_cbars[i]
            
            if self._img_handles[i] is None:
                # Initial draw
                self._img_handles[i] = ax_img.imshow(
                    plane_data, 
                    aspect='auto', 
                    origin='lower', 
                    interpolation='none',
                    cmap=self._current_cmap,
                    vmin=vmin,
                    vmax=vmax
                )
                
                # Set initial limits
                ax_img.set_ylim(0, self._plane_sizes[i])
                ax_img.set_xlim(0, N_ticks)
                ax_col.set_ylim(0, self._plane_sizes[i])
                
                # Create colorbar
                self._cbar_handles[i] = self._fig.colorbar(
                    self._img_handles[i], 
                    cax=ax_cbar, 
                    orientation='vertical'
                )
                
            else:
                # Subsequent draw: update data, colormap, and limits
                self._img_handles[i].set_data(plane_data)
                self._img_handles[i].set_cmap(self._current_cmap)
                
                # If the data processing changed (e.g., median subtraction toggled), 
                # reset color limits to the calculated vmin/vmax, otherwise preserve user zoom.
                if self._median_subtraction_active or is_initial_setup:
                    self._img_handles[i].set_clim(vmin, vmax)
                
                # Update colorbar to reflect changes in image data/limits
                self._cbar_handles[i].update_normal(self._img_handles[i])


        # 2. Update 1D Plots and Cursors
        self._update_1d_plots(data, N_channels, N_ticks, is_initial_setup)
        
        self._fig.canvas.draw_idle()

    def _on_cbar_scroll(self, event):
        """Handles mouse scroll events on a colorbar axis to zoom color limits."""
        if event.inaxes not in self._ax_cbars:
            return

        cbar_index = self._ax_cbars.index(event.inaxes)
        img_handle = self._img_handles[cbar_index]
        cbar_handle = self._cbar_handles[cbar_index]
        
        if img_handle is None:
            return

        vmin, vmax = img_handle.get_clim()
        data_range = vmax - vmin
        
        # Zoom factor (e.g., 10% per scroll step)
        zoom_factor = 0.1
        
        if event.button == 'up':
            # Zoom in (shrink range)
            new_range = data_range * (1 - zoom_factor)
        elif event.button == 'down':
            # Zoom out (expand range)
            new_range = data_range * (1 + zoom_factor)
        else:
            return

        # Center the new range around the current center
        center = (vmin + vmax) / 2
        new_vmin = center - new_range / 2
        new_vmax = center + new_range / 2
        
        img_handle.set_clim(new_vmin, new_vmax)
        cbar_handle.update_normal(img_handle)
        self._fig.canvas.draw_idle()

    def _on_cbar_click(self, event):
        """Handles mouse clicks on a colorbar axis for panning or resetting."""
        if event.inaxes not in self._ax_cbars:
            return

        cbar_index = self._ax_cbars.index(event.inaxes)
        img_handle = self._img_handles[cbar_index]
        cbar_handle = self._cbar_handles[cbar_index]
        
        if img_handle is None or event.ydata is None:
            return

        vmin, vmax = img_handle.get_clim()
        data_range = vmax - vmin
        
        if event.button == 1: # Left click: Pan
            # Calculate click position relative to current limits
            click_val = event.ydata
            center = (vmin + vmax) / 2
            
            # Calculate shift needed to center the clicked value
            shift = click_val - center
            
            new_vmin = vmin + shift
            new_vmax = vmax + shift
            
            img_handle.set_clim(new_vmin, new_vmax)
            cbar_handle.update_normal(img_handle)
            self._fig.canvas.draw_idle()

        elif event.button == 3: # Right click: Reset to calculated limits (symmetric or min/max)
            if self._current_frame:
                data = self._get_processed_data(self._current_frame)
                
                if self._median_subtraction_active:
                    max_abs = np.max(np.abs(data))
                    reset_vmin = -max_abs
                    reset_vmax = max_abs
                else:
                    reset_vmin = data.min()
                    reset_vmax = data.max()
                
                img_handle.set_clim(reset_vmin, reset_vmax)
                cbar_handle.update_normal(img_handle)
                self._fig.canvas.draw_idle()


    def _update_1d_plots(self, data: np.ndarray, N_channels: int, N_ticks: int, is_initial_setup: bool):
        """Updates the row/column plots and cursor lines."""
        
        # Ensure selected indices are within bounds
        global_row = max(0, min(self._selected_global_row, N_channels - 1))
        col = max(0, min(self._selected_col, N_ticks - 1))
        
        # --- Row Plot (Time profile for selected channel) ---
        
        # Save current X limits before clearing, as clearing resets limits even on shared axes
        current_xlim = None
        if not is_initial_setup and self._ax_row:
            current_xlim = self._ax_row.get_xlim()
            
        # Optimization: Avoid clearing if possible, update line data instead
        if self._row_line_handle is None:
            self._ax_row.clear()
            self._row_line_handle, = self._ax_row.plot(data[global_row, :], color='C0', drawstyle='steps-mid')
        else:
            self._row_line_handle.set_ydata(data[global_row, :])
            # We still need to update titles/labels/cursors, but avoid clearing the axis
            
        self._ax_row.set_title(f"Global Channel {global_row} Profile")
        self._ax_row.set_xlabel("Ticks")
        self._ax_row.set_ylabel("Amplitude")
        self._ax_row.grid()
        
        # Update X limits and autoscale Y
        if is_initial_setup:
            self._ax_row.set_xlim(0, N_ticks)
        elif current_xlim is not None:
            self._ax_row.set_xlim(current_xlim)
            
        # Re-evaluate limits based on new data
        self._ax_row.relim()
        self._ax_row.autoscale_view(tight=True, scalex=False, scaley=True)
        
        # Handle vertical cursor on row plot (must be redrawn if axis wasn't cleared)
        # Since we are avoiding ax.clear(), we need to manage the cursor line explicitly.
        # For simplicity and robustness against autoscale, we will manage the cursor lines 
        # in the loop below where we clear image cursors.
        
        # --- Column Plots (Channel profiles for selected tick) ---
        
        # Clear previous cursors from image plots and row plot
        for line in self._ax_row.lines:
            if line is not self._row_line_handle:
                line.remove()
        self._ax_row.axvline(col, color='r', linestyle=':', linewidth=1)


        for ax_img in self._ax_imgs:
            # Iterate and remove lines (cursors)
            for line in ax_img.lines:
                line.remove()
            
        
        for i in range(self.N_PLANES):
            ax_col = self._ax_cols[i]
            ax_img = self._ax_imgs[i]
            
            start_ch = self._plane_offsets[i]
            end_ch = start_ch + self._plane_sizes[i]
            plane_data_col = data[start_ch:end_ch, col]
            plane_size = self._plane_sizes[i]
            
            # Local row index within this plane
            local_row = global_row - start_ch
            
            # Save current Y limits for column plot before clearing
            current_ylim = None
            if not is_initial_setup and ax_col:
                current_ylim = ax_col.get_ylim()
                
            
            # Optimization: Update line data instead of clearing
            if self._col_line_handles[i] is None:
                ax_col.clear()
                # Plot data[0:plane_size, col] against local channel index (0 to plane_size)
                self._col_line_handles[i], = ax_col.plot(plane_data_col, np.arange(plane_size), color=f'C{i+1}', drawstyle='steps-mid')
            else:
                # Update X data (amplitude) and Y data (channel index, which is constant)
                self._col_line_handles[i].set_xdata(plane_data_col)
                # Note: Y data (np.arange(plane_size)) is constant for a given plane size, no need to update
            
            ax_col.set_title(f"Plane {i} Tick {col}")
            ax_col.set_xlabel("Amplitude")
            
            # Restore or set initial Y limits
            if is_initial_setup:
                ax_col.set_ylim(0, plane_size)
            elif current_ylim is not None:
                ax_col.set_ylim(current_ylim)
                
            # Re-evaluate limits based on new data
            ax_col.relim()
            ax_col.autoscale_view(tight=True, scalex=True, scaley=False)
            #ax_col.invert_xaxis() 
            ax_col.grid()
            
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
            ax_img.grid()


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
            
            # When clicking, we are updating the cursor position, not initializing the figure.
            processed_data = self._get_processed_data(self._current_frame)
            self._update_1d_plots(processed_data, N_channels, N_ticks, is_initial_setup=False)

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
