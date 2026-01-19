def trio(gui, frame):
    '''
    Return a "trio" style gui
    '''
    if gui == 'mpl':
        mpl_trio(frame)
    return qt_trio(frame)

def mpl_trio(frame):
    import matplotlib.pyplot as plt
    from .trio import TrioDisplay
    disp = TrioDisplay()
    disp.show(frame)
    plt.show()
    
def qt_trio(frame):
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication([])
    from .qtrio import QtTrioDisplay
    gui = QtTrioDisplay()
    gui.show_frame(frame)
    app.exec()
    
