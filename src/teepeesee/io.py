# Functions to read and write and otherwise deal with files. 
import numpy as np
from typing import Dict, List

class Frame:
    """Holds the trio of numpy arrays for a single event."""
    def __init__(self, frame: np.ndarray, channels: np.ndarray, tickinfo: np.ndarray, event_number: int):
        self.frame = frame
        self.channels = channels
        self.tickinfo = tickinfo
        self.event_number = event_number

class Data:
    """
    Provides a list-like interface to trios of numpy arrays found in an NPZ file.
    Each item returned is a Frame instance.
    
    The arrays are grouped by event number based on the naming convention:
    category_tag_event_number (e.g., frame_*_1, channels_raw_1, tickinfo_foo_1).
    """
    def __init__(self, npz_path: str):
        self._data: Dict[int, Dict[str, np.ndarray]] = self._load_and_group_data(npz_path)
        # Store event numbers sorted numerically to provide list interface ordering
        self._event_numbers: List[int] = sorted(self._data.keys())

    def _load_and_group_data(self, npz_path: str) -> Dict[int, Dict[str, np.ndarray]]:
        try:
            npz_file = np.load(npz_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"NPZ file not found at {npz_path}")
        except Exception as e:
            # Catch general numpy loading errors
            raise IOError(f"Error loading NPZ file {npz_path}: {e}")

        grouped_data: Dict[int, Dict[str, np.ndarray]] = {}
        required_categories = {"frame", "channels", "tickinfo"}

        for name in npz_file.files:
            # Expected format: category_tag_event_number
            parts = name.split('_')
            
            if len(parts) < 3:
                continue

            category = parts[0]
            
            if category not in required_categories:
                continue

            try:
                # The event number is the last part
                event_number = int(parts[-1])
            except ValueError:
                continue

            if event_number not in grouped_data:
                grouped_data[event_number] = {}
            
            # Store the array under its category name
            grouped_data[event_number][category] = npz_file[name]

        # Filter to ensure only complete trios are kept
        valid_data = {}
        for event_num, trio in grouped_data.items():
            if set(trio.keys()) == required_categories:
                valid_data[event_num] = trio

        return valid_data

    def __len__(self) -> int:
        """Returns the number of complete event trios found."""
        return len(self._event_numbers)

    def __getitem__(self, index: int) -> Frame:
        """Returns the Frame corresponding to the event at the given index."""
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        
        if index < 0 or index >= len(self._event_numbers):
            raise IndexError("Index out of range")

        event_number = self._event_numbers[index]
        trio = self._data[event_number]
        
        return Frame(
            frame=trio["frame"],
            channels=trio["channels"],
            tickinfo=trio["tickinfo"],
            event_number=event_number
        )
