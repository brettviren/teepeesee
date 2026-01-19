import sys
import click
from qtpy import QtWidgets as qw
from .gui import MainWindow
import pyqtgraph as pg
pg.setConfigOption('imageAxisOrder', 'row-major')

@click.command()
@click.argument('files', nargs=-1, type=click.Path())
def main(files):
    """Display LArTPC detector data from NPZ files.

    FILES: One or more NPZ files to display. If none provided, opens with demo data.
    """
    qw.QApplication.setApplicationName("cueteepeesee")
    qw.QApplication.setOrganizationName("teepeesee")

    # Only pass program name to QApplication to avoid conflicts with click arguments
    app = qw.QApplication(sys.argv[:1])
    files_to_open = list(files) if files else None
    window = MainWindow(initial_files=files_to_open)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
