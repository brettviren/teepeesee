from .qt import QtWidgets, pg
class Framelet(QtWidgets.QtWidget):
    '''
    A GUI to display one framelet.

    | colorbar | 2D image view | chan proj |
    | ui1      | tick proj     | ui2       |

    '''

    def __init__(self, shape, parent=None):
        '''
        Create assuming given shape for the framelet array
        '''
        super().__init__(parent)

        self.setWindowTitle("Teepeesee")

        layout = QtWidgets.QGridLayout()

        # 2D view
        view_plot = pg.PlotWidget(labels={'left':'Channels'})
        view_item = pg.ImageItem()
        view_plot.addItem(view_item)
        view_plot.setMouseEnabled(x=True, y=True)

        colorbar = pg.HistogramLUTWidget()
        colorbar.setImageItem(view_item)
        colorbar.item.gradient.loadPreset('viridis')
        view_item.setLevels((-1,1))
        
        auto_range_button = QPushButton('Auto Range\n(-2σ to +2σ)')
        def update_colormap():
            view_item.setLevels((self.spectrogram_min, self.spectrogram_max))
            colorbar.setLevels(self.spectrogram_min, self.spectrogram_max)
        auto_range_button.clicked.connect(update_colormap)


        # channel projection
        chan_plot = pg.PlotWidget(lables={'left':'Channels'})
        chan_plot.setMouseEnabled(x=True, y=True)
        chan_plot.setYRange(0, shape[1])

        # time projection
        time_plot = pg.PlotWidget(lables={'bottom':'Time [ticks]'})
        time_plot.setMouseEnabled(x=True, y=True)
        time_plot.setYRange(0, shape[1])
        time_plot_curve_i = time_plot.plot([]) 
        time_plot_curve_q = time_plot.plot([]) 



        layout.addWidget(auto_range_button, 3, 1)
        layout.addWidget(time_plot, 1, 0)        
