import sys
from PyQt5 import QtCore, QtGui, QtWidgets
import AOConfig as cfg

cfg.APP_NAME = 'RPE Detection'
cfg.APP_VERSION = '1.1.2 (2022-03-03)'

if __name__ == '__main__':
    try:
        cdir = os.path.dirname(__file__)
        os.chdir(cdir)
        # print(cdir)
    except Exception:
        pass
    import AOMainWindow
    app = QtWidgets.QApplication([])
    app.setApplicationName(cfg.APP_NAME)
    window = AOMainWindow.MainWindow()
    window.show()
    if len(sys.argv) > 1:
        flist = cfg.InputList(sys.argv[1:])
        img_filenames = flist.get_files(('.tif', '.tiff'))
        if len(img_filenames) > 0:
            window._open_image_list(img_filenames, True)
            csv_filenames = flist.get_files('.csv')
            if len(csv_filenames) > 0:
                window._open_annotation_list(csv_filenames)
    sys.exit(app.exec_())