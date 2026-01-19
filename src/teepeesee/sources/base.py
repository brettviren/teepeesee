from qtpy import QtCore as qc

class DataSource(qc.QObject):
    dataReady = qc.Signal(list)
    def __init__(self, index=0, name=None):
        super().__init__()
        self._index = index
        self._layer = 0
        self._name = name

    @property
    def index(self):
        return self._index
    @property
    def layer(self):
        return self._layer
    @property
    def name(self):
        if self._name:
            return self._name
        return "base"


class SourceManager(qc.QObject):
    """Manages multiple synchronized data sources."""
    dataReady = qc.Signal(list)
    indexChanged = qc.Signal(int)
    sourceAdded = qc.Signal(object)  # Emits the source object when added
    sourceSelected = qc.Signal(object)  # Emits the source object when selected

    def __init__(self):
        super().__init__()
        self._sources = []
        self._current_source = None
        self._index = 0
        self._layer = 0
        self._cached_data = {}  # Maps source to its last emitted data

    @property
    def index(self):
        return self._index

    @property
    def layer(self):
        return self._layer

    @property
    def name(self):
        """Return combined names of all sources."""
        if not self._sources:
            return "No sources"
        return " + ".join(s.name for s in self._sources)

    def add_source(self, source):
        """Add a data source to the manager."""
        # Initialize cache for this source
        self._cached_data[source] = []

        # Set the source's index to match the manager's current index
        if hasattr(source, 'jump'):
            source.jump(self._index)
        if hasattr(source, 'setLayer'):
            source.setLayer(self._layer)

        # Connect the source's dataReady signal to cache and aggregate
        def cache_and_aggregate(data):
            self._cached_data[source] = data
            self._aggregate_and_emit()

        source.dataReady.connect(cache_and_aggregate)
        self._sources.append(source)

        # Set as current source if this is the first source
        if len(self._sources) == 1:
            self._current_source = source

        # Emit sourceAdded signal
        self.sourceAdded.emit(source)

    def _aggregate_and_emit(self):
        """Aggregate data from sources and emit."""
        all_parts = []

        # If a current source is selected, only emit its data
        if self._current_source and self._current_source in self._cached_data:
            all_parts = self._cached_data[self._current_source]
        else:
            # Otherwise, aggregate all sources
            for source in self._sources:
                if source in self._cached_data:
                    all_parts.extend(self._cached_data[source])

        if all_parts:
            self.dataReady.emit(all_parts)

    def select_source(self, name):
        """Select a source by name and emit sourceSelected signal."""
        for source in self._sources:
            if source.name == name:
                self._current_source = source
                self.sourceSelected.emit(source)
                # Re-emit the current source's data
                self._aggregate_and_emit()
                return
        print(f"Warning: Source with name '{name}' not found")

    def get_all_sources_data(self):
        """Get cached data from all sources (for RGB Multi mode).

        Returns: list of lists, where each inner list is the parts from one source
        """
        all_data = []
        for source in self._sources:
            if source in self._cached_data:
                all_data.append(self._cached_data[source])
        return all_data

    def get_current_source_data(self):
        """Get cached data from the current source only.

        Returns: list of parts from current source, or empty list if no current source
        """
        if self._current_source and self._current_source in self._cached_data:
            return self._cached_data[self._current_source]
        return []

    @qc.Slot()
    def prev(self):
        """Go to previous index."""
        self._index = max(0, self._index - 1)
        self.indexChanged.emit(self._index)
        for source in self._sources:
            if hasattr(source, 'prev'):
                source.prev()

    @qc.Slot()
    def next(self):
        """Go to next index."""
        self._index += 1
        self.indexChanged.emit(self._index)
        for source in self._sources:
            if hasattr(source, 'next'):
                source.next()

    @qc.Slot(int)
    def jump(self, idx):
        """Jump to specific index."""
        self._index = max(0, idx)
        self.indexChanged.emit(self._index)
        for source in self._sources:
            if hasattr(source, 'jump'):
                source.jump(idx)

    @qc.Slot(int)
    def setLayer(self, layer):
        """Set the layer for all sources."""
        if self._layer != layer:
            self._layer = layer
            for source in self._sources:
                if hasattr(source, 'setLayer'):
                    source.setLayer(layer)
