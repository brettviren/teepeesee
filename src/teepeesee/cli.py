import sys
from qtpy import QtWidgets as qw
from .gui import MainWindow
import pyqtgraph as pg
pg.setConfigOption('imageAxisOrder', 'row-major')

# --- Main Window ---
def main():
    qw.QApplication.setApplicationName("cueteepeesee")
    qw.QApplication.setOrganizationName("teepeesee")

    app = qw.QApplication(sys.argv)
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    window = MainWindow(initial_files=files)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
