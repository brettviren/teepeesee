from pathlib import Path
from collections import defaultdict
import numpy

# map number of channels to a detector name
detector_map = {
    2560: "apa",
    1600: "apauv",
    960: "apacol",
    800: "apaind",
}

# map detector names to channel break-down per plane

plane_sizes_map = {
    "apa": (800, 800, 960),
    "apauv": (800, 800),
    "apaind": (800,),
    "apacol": (960,),
}

def plane_sizes(nchans):
    try:
        dname = detector_map[nchans]
        return plane_sizes[dname]
    except KeyError:
        return (nchans,)
    


class Framelet:
    '''
    A framelet represents part of a readout (frame) with a contiguous subset
    of channels.

    Note, a frame mayhave zero (channel) size
    '''
    # fixme: handle case where we are given less than one apa worth of channels.
    def __init__(self, frame, offset, size, index):
        '''
        Make a framelet starting at channel offset and spanning size in
        plane index of parent frame.
        '''
        self.frame=frame
        self.offset=offset
        self.size=size
        self.index=index;

    @property
    def samples(self):
        '''
        The waveform samples 2D array.
        '''
        self.frame.samples[self.offset:self.offset+self.size]


class Frame:
    '''
    A frame represents the readout of all channels from one detector anode
    plane (APA/CRU).

    It is primarily composed of framelets.
    '''
    def __init__(self, fobj, evt, tag="*"):
        self.fobj = fobj
        self.evt = evt
        self.tag = tag

    @property
    def filename(self):
        return self.fobj.fid.name

    def _make_framelets(self):
        farr = self.fobj[f'frame_{self.tag}_{self.evt}']
        nchan, ntick = farr.shape
        framelets = list()
        poffset = 0
        for pindex, psize in enumerate(plane_sizes(nchan)):
            framelets.append(Framelet(self, poffset, psize, pindex))
            poffset += psize
        self._framelets = framelets
        

    @property
    def framelets(self):
        '''
        A list of framelets in this frame.
        '''
        if not hasattr(self, '_framelets'):
            self._make_framelets()
        return self._framelets


    @property
    def samples(self):
        '''
        The samples aka frame array.
        '''
        if not hasattr(self, '_array'):
            self._array = fobj[f'frame_{self._tag}_{self.evt}']
        return self._array

    @property
    def channels(self):
        '''
        The channels array.
        '''
        if not hasattr(self, '_channels'):
            self._channels = fobj[f'channels_{self._tag}_{self.evt}']
        return self._channels


class FrameSet:
    '''
    A set of coincident frames (same evt) and across different tiers
    (tag and/or file source).

    Framelets in the set may populate different planes.

    '''
    def __init__(self, frames = None):
        self.frames = frames or list()

    def append(self, frame):
        self.frames.append(frame)

    @property
    def nplanes(self):
        '''
        Number of unique planes spanned by the frame's framelets
        '''
        indices = set()
        for frame in self.frames:
            for fl in frame.framelets
            indices.add(fl.index)
        return len(indices)


def make_frame_sets(paths):
    '''
    Return dict mapping evt number to frame set.
    '''
    by_evt = defaultdict(FrameSet)
    for path in paths:
        fobj = numpy.load(path)
        for array_name in fobj.files:
            parts = array_name.split('_')
            cat = parts[0]
            if cat != "frame":
                continue
            tag = '_' .join(list(parts[1:-1]))
            evt = int(parts[-1])
            by_evt[evt].append(Frame(fobj, evt, tag))
    return by_evt


class Data:
    '''
    Data represents a sequence of frame sets.

    We assume each frame set is equally shaped.
    '''

    def __init__(self, paths):
        self.by_evt = make_frame_sets(paths)

    def __len__(self) -> int:
        return len(self.by_evt)

    def __getitem__(self, index: int) -> Frame:
        key = self.by_evt.keys()[index]
        return self.by_evt[key]


    @property
    def nplanes(self):
        return max([x.nplanes for x in self.by_evt.values()])
        
