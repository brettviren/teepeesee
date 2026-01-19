"""Data transformation operations for frame display pipeline.

Each operation is a callable that takes numpy array(s) and returns transformed array(s).
Operations are stateless and can be composed in a pipeline.
"""

import numpy as np


class Rebaseline:
    """Subtract median baseline from each channel (row)."""

    def __call__(self, data):
        """Apply baseline subtraction.

        Args:
            data: numpy array of shape (nchans, nticks) or list of such arrays

        Returns:
            Baseline-subtracted array(s) with same shape as input
        """
        if isinstance(data, list):
            return [self._rebaseline_single(d) for d in data]
        return self._rebaseline_single(data)

    def _rebaseline_single(self, samples):
        """Apply baseline subtraction to a single array."""
        return samples - np.median(samples, axis=1, keepdims=True)


class UnitNorm:
    """Normalize data to [0, 1] range for RGB multi-source display."""

    def __call__(self, data):
        """Apply unit normalization.

        Args:
            data: numpy array of shape (nchans, nticks) or list of such arrays

        Returns:
            Normalized array(s) with values in [0, 1] range
        """
        if isinstance(data, list):
            return [self._normalize_single(d) for d in data]
        return self._normalize_single(data)

    def _normalize_single(self, samples):
        """Normalize a single array to [0, 1]."""
        data_min, data_max = np.nanmin(samples), np.nanmax(samples)
        if data_max > data_min:
            return (samples - data_min) / (data_max - data_min)
        return np.zeros_like(samples)
