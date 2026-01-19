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
# Qt-based display (click-based CLI)
# Uses QtPy wrapper for Qt compatibility (PyQt6, PyQt5, PySide2, PySide6)
qtpc frame-file.npz [...]

# Start with no files and use random demo data
qtpc

# Show help
qtpc --help
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

The input data is modeled as a `DataSource` class.  Each different kind of input from file has its own `FileSource` class.  A data source represents a discrete location or **index** in a stream of data.  At each **index** is a list of **parts** and each **part** is dict with these keys:

- `samples` :: a numpy array of at least 2 dimensions of shape `(nchan, ntick)` giving a 2D image.  If the array is 3D then it has shape `(nfeat, nchan, ntick)` where `nfeat` gives some number of features.
- `channels` :: a numpy array of detector electronics channel ID number labeling each row of the `nchan` dimension.
- `tickinfo` :: a length-3 array of `(start_time, sample_period, nchan)`

The project currently supports two file data sources, both as `.npz` numpy zip file format and with these schema:

1. **Frame Schema** (Wire-Cell "frame" format)
   - Arrays named: `frame_<tag>_<index>`, `channels_<tag>_<index>`, `tickinfo_<tag>_<index>`
   - Three with common `<tag>` and `<index>` contribute to the parts of the index.
   - The `<tag>` may have underscores.
   - The `frame_<tag>_<index>` and `channels_<tag>_<index>` arrays are each concatenations of multiple parts.  The `DETECTOR_MAP` maps the `nchan` dimension size to a name and a "splits".  The "splits" tuple shows how to partition the two arrays along the `nchan` dimension to make parts.

2. **Tensor Schema**: (Wire-Cell "tensor" format) is a generalization of the "frame" format.
   - Arrays named: `tensor_<index>_<plane>_array`, `tensor_<index>_<plane>_metadata.json`
   - Supports 3D arrays with feature dimensions (layers)
   - Here, we assume the "frame" model is expressed in the "tensor schema" and each `<plane>` array is one **part** for the index.  Each array provides one `samples` array.
   - Each `<plane>` is an integer counting a **part**.
   - The JSON file provides metadata about the corresponding array.


### Data Flow

The application is reactive via signal/slot.  Every `DataSource` has a
`dataReady` signal that emits the list of parts.

### GUI Architecture

QtPy GUI widgets with pyqtgraph-based data display widgets.

   - Uses QtPy wrapper for Qt binding compatibility (supports PyQt6, PyQt5, PySide2, PySide6)
   - Signal/slot architecture for UI updates
   - Three `FrameDisplay` widgets stacked vertically (one per plane)
   - Synchronized vertical crosshairs (selecting a common time tick, aka image column) , independent horizontal positions (selecting individual detector electronics channels, aka image rows).
   - Features: multiple colormaps, baseline subtraction, auto-contrast, grid toggle, layer navigation for 3D data

### Key Components

The main Qt application has been modularized:

- **`cli.py`**: Click-based CLI entry point for `qtpc` command, handles argument parsing
- **`gui.py`**: MainWindow and GUI construction
- **`displays.py`**: Data display widgets
- **`sources/*.py`**: Classes for data sources.

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
bd comments add <id> "The comment" # To add a comment 
bd close <id>
bd sync               # Sync with git
```

## Important Notes

- The Qt application uses **QtPy** wrapper for Qt binding compatibility
  - Supports multiple Qt backends: PyQt6 (default), PyQt5, PySide2, PySide6
  - Set `QT_API` environment variable to choose backend (e.g., `export QT_API=pyqt6`)
- The Qt application uses **row-major** image axis order (y, x) for consistency with numpy
- NPZ files can contain multiple events and multiple data tiers (tags)
- Frame data is channel-major: shape is `(n_channels, n_ticks)`
- `tickinfo` array: `[start_time, sample_period, num_samples]` in Wire-Cell units (nanoseconds)
- When modifying the Qt UI, be aware of signal/slot spaghetti (noted as future refactoring target)
