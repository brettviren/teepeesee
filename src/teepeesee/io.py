# Functions to read and write and otherwise deal with files. 
import numpy as np
from typing import Dict, List, Tuple

# Lookup table for detector names based on the number of channels (rows in frame array)
_DETECTOR_MAP: Dict[int, str] = {
    2560: "apa",
}

# Lookup table for plane sizes based on detector name
_PLANE_SIZES_MAP: Dict[str, List[int]] = {
    "apa": [800, 800, 960],
}

class Frame:
    """Holds the trio of numpy arrays for a single event."""
    def __init__(self, frame: np.ndarray, channels: np.ndarray, tickinfo: np.ndarray, event_number: int):
        if len(frame.shape) != 2:
            raise ValueError("frame array must be 2D")
        
        # Corrected array size checks: use .size attribute for 1D arrays
        if frame.shape[0] != channels.size:
            raise ValueError("frame and channels array do not match")
        if tickinfo.size != 3:
            raise ValueError("wrong size tickinfo")

        self.frame = frame
        self.channels = channels
        self.tickinfo = tickinfo
        self.event_number = event_number

    @property
    def tstart(self):
        '''
        The start time of the original IFrame (see .tbin) 
        '''
        return self.tickinfo[0]

    @property
    def tick(self):
        '''
        The sample period time in WCT system of units.
        '''
        return self.tickinfo[1]

    @property
    def tbin(self):
        '''
        How many samples between the start time and the first column of the frame array.
        '''
        return self.tickinfo[2]

    def detector(self) -> str:
        """
        Returns the detector name based on the number of channels (rows in the frame array).
        If the channel count is unknown, returns "det<channel_count>".
        """
            
        n_channels = self.frame.shape[0]
        
        return _DETECTOR_MAP.get(n_channels, f"det{n_channels}")

    def plane_sizes(self) -> List[int]:
        """
        Returns the sizes of the three channel planes for the current detector.
        If the detector is unknown, splits the total channel count into three 
        approximately equal parts, giving the remainder to the third plane.
        """
        detector_name = self.detector()
        
        if detector_name in _PLANE_SIZES_MAP:
            return _PLANE_SIZES_MAP[detector_name]
        
        # Handle unregistered detector: split channels into 3 approximately equal parts
        n_channels = self.frame.shape[0]
        
        n1 = n_channels // 3
        n2 = n_channels // 3
        n3 = n_channels - n1 - n2 # n3 gets the remainder
        
        return [n1, n2, n3]


class Data:
    """
    Provides a list-like interface to trios of numpy arrays found in an NPZ file.
    Each item returned is a Frame instance.
    
    The arrays are grouped by event number based on the naming convention:
    category_tag_event_number (e.g., frame_*_1, channels_raw_1, tickinfo_foo_1).
    
    Data loading is performed lazily upon access via __getitem__.
    """
    # Maps event number to a tuple of array names: (frame_name, channels_name, tickinfo_name)
    _EventMap = Dict[int, Dict[str, str]]

    def __init__(self, npz_path: str):
        self._npz_path = npz_path
        self._event_map: Data._EventMap
        self._event_numbers: List[int]
        
        self._event_map, self._event_numbers = self._parse_array_names(npz_path)

    def _parse_array_names(self, npz_path: str) -> Tuple[_EventMap, List[int]]:
        """Reads array names from the NPZ file and groups them by event number."""
        try:
            # Load the file structure without loading data
            npz_file = np.load(npz_path)
            array_names = npz_file.files
            # Close the file handle immediately if np.load opened it, 
            # although np.load usually returns an NpzFile object which manages access.
            # We rely on accessing .files which doesn't load data.
        except FileNotFoundError:
            raise FileNotFoundError(f"NPZ file not found at {npz_path}")
        except Exception as e:
            raise IOError(f"Error accessing NPZ file structure {npz_path}: {e}")

        grouped_names: Dict[int, Dict[str, str]] = {}
        required_categories = {"frame", "channels", "tickinfo"}

        for name in array_names:
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

            if event_number not in grouped_names:
                grouped_names[event_number] = {}
            
            # Store the array name under its category
            grouped_names[event_number][category] = name

        # Filter to ensure only complete trios are kept
        event_map: Data._EventMap = {}
        for event_num, trio in grouped_names.items():
            if set(trio.keys()) == required_categories:
                event_map[event_num] = trio

        # Store event numbers sorted numerically
        event_numbers: List[int] = sorted(event_map.keys())
        
        return event_map, event_numbers

    def __len__(self) -> int:
        """Returns the number of complete event trios found."""
        return len(self._event_numbers)

    def __getitem__(self, index: int) -> Frame:
        """
        Returns the Frame corresponding to the event at the given index, 
        loading the required arrays from the NPZ file.
        """
        if not isinstance(index, int):
            raise TypeError("Index must be an integer")
        
        if index < 0 or index >= len(self._event_numbers):
            raise IndexError("Index out of range")

        event_number = self._event_numbers[index]
        name_map = self._event_map[event_number]
        
        # Load the specific arrays for this event
        try:
            with np.load(self._npz_path) as npz_file:
                frame_array = npz_file[name_map["frame"]]
                channels_array = npz_file[name_map["channels"]]
                tickinfo_array = npz_file[name_map["tickinfo"]]
        except Exception as e:
            raise IOError(f"Error loading data for event {event_number} from {self._npz_path}: {e}")
        
        return Frame(
            frame=frame_array,
            channels=channels_array,
            tickinfo=tickinfo_array,
            event_number=event_number
        )
