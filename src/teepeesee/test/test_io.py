import numpy as np
import pytest
from pathlib import Path

# Assuming teepeesee is installed or accessible via PYTHONPATH
from teepeesee.io import Data, Frame

@pytest.fixture
def sample_npz_file(tmp_path: Path) -> Path:
    """
    Generates a temporary NPZ file containing a single event trio.
    Event number: 1, Tag: 'test'
    """
    event_num = 1
    tag = "test"
    
    # Define array names according to convention: category_tag_event_number
    frame_name = f"frame_{tag}_{event_num}"
    channels_name = f"channels_{tag}_{event_num}"
    tickinfo_name = f"tickinfo_{tag}_{event_num}"

    # Define array contents
    frame_data = np.arange(10 * 100, dtype=np.float32).reshape((10, 100))
    channels_data = np.arange(10, dtype=np.int32)
    tickinfo_data = np.array([100, 50, 1], dtype=np.int32)

    # Create the NPZ file
    npz_path = tmp_path / "test_data.npz"
    np.savez(
        npz_path,
        **{frame_name: frame_data, channels_name: channels_data, tickinfo_name: tickinfo_data}
    )
    
    # Add some junk data to ensure parsing works correctly
    np.savez(
        npz_path,
        junk_array=np.array([1, 2, 3]),
        frame_incomplete_2=np.zeros((1,1)),
        **{frame_name: frame_data, channels_name: channels_data, tickinfo_name: tickinfo_data}
    )

    return npz_path

@pytest.fixture
def sample_npz_file_apa(tmp_path: Path) -> Path:
    """
    Generates a temporary NPZ file containing an APA event trio (2560 channels).
    Event number: 10, Tag: 'apa_test'
    """
    event_num = 10
    tag = "apa_test"
    N_CHANNELS = 2560
    N_TICKS = 100
    
    frame_name = f"frame_{tag}_{event_num}"
    channels_name = f"channels_{tag}_{event_num}"
    tickinfo_name = f"tickinfo_{tag}_{event_num}"

    frame_data = np.zeros((N_CHANNELS, N_TICKS), dtype=np.float32)
    channels_data = np.arange(N_CHANNELS, dtype=np.int32)
    tickinfo_data = np.array([100, 50, 1], dtype=np.int32)

    npz_path = tmp_path / "test_data_apa.npz"
    np.savez(
        npz_path,
        **{frame_name: frame_data, channels_name: channels_data, tickinfo_name: tickinfo_data}
    )
    return npz_path


def test_data_initialization_and_length(sample_npz_file: Path):
    """Test if Data initializes correctly and finds the single event."""
    data = Data(str(sample_npz_file))
    assert len(data) == 1
    # Check internal event number tracking
    assert data._event_numbers == [1]

def test_data_getitem_and_lazy_loading(sample_npz_file: Path):
    """Test if __getitem__ loads the correct Frame and data lazily."""
    data = Data(str(sample_npz_file))
    
    # Access the first (and only) item
    frame: Frame = data[0]
    
    # Check Frame attributes
    assert isinstance(frame, Frame)
    assert frame.event_number == 1
    
    # Check array shapes and content
    assert frame.frame.shape == (10, 100)
    assert frame.channels.shape == (10,)
    assert frame.tickinfo.shape == (3,)
    
    # Verify content (checking a few values)
    expected_frame_data = np.arange(10 * 100, dtype=np.float32).reshape((10, 100))
    assert np.array_equal(frame.frame, expected_frame_data)
    assert np.array_equal(frame.channels, np.arange(10, dtype=np.int32))
    assert frame.tickinfo[0] == 100

def test_frame_detector_known(sample_npz_file_apa: Path):
    """Test detector identification for a known channel count (APA)."""
    data = Data(str(sample_npz_file_apa))
    frame: Frame = data[0]
    
    assert frame.frame.shape[0] == 2560
    assert frame.detector() == "apa"

def test_frame_detector_unknown(sample_npz_file: Path):
    """Test detector identification for an unknown channel count (10)."""
    data = Data(str(sample_npz_file))
    frame: Frame = data[0]
    
    assert frame.frame.shape[0] == 10
    assert frame.detector() == "det10"


def test_data_index_errors(sample_npz_file: Path):
    """Test boundary conditions for indexing."""
    data = Data(str(sample_npz_file))
    
    with pytest.raises(IndexError):
        _ = data[1]
    
    with pytest.raises(IndexError):
        _ = data[-1]

def test_data_file_not_found():
    """Test handling of non-existent file."""
    with pytest.raises(FileNotFoundError):
        Data("non_existent_file.npz")

def test_data_incomplete_trio(tmp_path: Path):
    """Test that incomplete trios are ignored."""
    npz_path = tmp_path / "incomplete.npz"
    np.savez(
        npz_path,
        # Complete trio for event 1
        frame_test_1=np.zeros((1,1)),
        channels_test_1=np.zeros((1,)),
        tickinfo_test_1=np.zeros((3,)), # Now complete
        
        # Incomplete trio for event 2 (missing channels and tickinfo)
        frame_test_2=np.zeros((1,1)) 
    )
    
    data = Data(str(npz_path))
    # Only event 1 should be counted
    assert len(data) == 1
    assert data._event_numbers == [1]
