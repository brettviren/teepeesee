# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**teepeesee** is a Python-based visualization tool for Wire-Cell Toolkit LArTPC (Liquid Argon Time Projection Chamber) detector data. It provides GUI interfaces to display and analyze time-series detector readout frames stored in NPZ files.

## Development Commands

### Installation
```bash
# Install as tool (recommended for users)
uv tool install git+https://github.com/brettviren/teepeesee

# Install in development mode
uv pip install -e .
```

### Running the Applications
```bash
# Matplotlib-based display (older, slower)
teepeesee display frame-file.npz
teepeesee mdisplay frame-file.npz [...]

# PyQt6-based display (newer, faster, recommended)
cueteepeesee frame-file.npz [...]

# Random demo data (no file needed)
cueteepeesee
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest src/teepeesee/test/test_io.py

# Run with verbose output
pytest -v
```

## Architecture

### Data Model

The project uses two main data schemas:

1. **Frame Schema** (Wire-Cell format): Used by `io.py` and `trio.py`
   - Arrays named: `frame_<tag>_<event_num>`, `channels_<tag>_<event_num>`, `tickinfo_<tag>_<event_num>`
   - A "Frame" represents one complete detector readout event
   - Each frame is split into 3 channel planes (U, V, Collection) with detector-specific channel counts

2. **Tensor Schema**: Used by `cueteepeesee.py` for more general data
   - Arrays named: `tensor_<index>_<plane>_array`, `tensor_<index>_<plane>_metadata.json`
   - Supports 3D arrays with feature dimensions (layers)

### Data Flow

```
NPZ File → Data/DataSource → Frame/FrameSet → Display Widget
```

- **Data classes** (`io.Data`, `mio.Data`): Parse NPZ files, provide list-like access to frames
- **DataSource classes** (`cueteepeesee.py`): Qt-based, emit signals when data changes
  - `FileSource`: Auto-detects schema, delegates to `FrameFileSource` or `TensorFileSource`
  - `RandomDataSource`: Generates synthetic data for testing
- **Frame/FrameSet**: Container for event data with channel/time metadata
- **Display classes**: Visualize frames with zooming, color mapping, crosshairs

### GUI Architecture

Two display implementations:

1. **Matplotlib-based** (`display.py`, `trio.py`, `mdisplay.py`):
   - Older, slower, simpler
   - `Display`: Single image view
   - `TrioDisplay`: Three plane views with independent scaling

2. **PyQt6/pyqtgraph-based** (`cueteepeesee.py`):
   - Modern, faster rendering
   - Signal/slot architecture for UI updates
   - Three `FrameDisplay` widgets stacked vertically (one per plane)
   - Synchronized vertical crosshairs, independent horizontal positions
   - Features: multiple colormaps, baseline subtraction, auto-contrast, grid toggle, layer navigation for 3D data

### Key Components

- **`__main__.py`**: Click-based CLI entry point for `teepeesee` command
- **`cueteepeesee.py`**: Main Qt application and entry point (850 lines, contains most Qt logic)
- **`io.py`**: Frame schema data loading with lazy evaluation
- **`mio.py`**: Alternative data loader (frame sets, less complete)
- **`trio.py`**: Matplotlib three-plane display
- **`display.py`**: Matplotlib single-image display
- **`qt.py`**: Qt/pyqtgraph import configuration (row-major image axis order)

### Detector Geometries

Detector configurations are hard-coded in `DETECTOR_MAP`:
- **apa** (2560 channels): 800 (U) + 800 (V) + 960 (Collection)
- **apauv** (1600 channels): 800 (U) + 800 (V)
- **apaind** (800 channels): Induction only
- **apacol** (960 channels): Collection only

Unknown detector sizes are split into three approximately equal planes.

## Issue Tracking

This project uses **beads** (`bd`) for issue tracking. See `AGENTS.md` for workflow details.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress
bd update <id> --description "Comment" # Add comment 
bd close <id>
bd sync               # Sync with git
```

## Important Notes

- The Qt application uses **row-major** image axis order (y, x) for consistency with numpy
- NPZ files can contain multiple events and multiple data tiers (tags)
- Frame data is channel-major: shape is `(n_channels, n_ticks)`
- `tickinfo` array: `[start_time, sample_period, num_samples]` in Wire-Cell units (nanoseconds)
- When modifying the Qt UI, be aware of signal/slot spaghetti (noted as future refactoring target)
