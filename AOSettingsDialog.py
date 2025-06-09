__all__ = ('BASE_DIR', 'ICONS_DIR', 'HELP_DIR', 'qt_icon', 'display_error', 'display_warning', 'askYesNo',
        'ao_progress_dialog', 'ao_loc_dialog', 'ao_parameter_dialog', 'ao_brightness_contrast',
        'ao_source_window',)

import os
import sys
import time
import datetime
import math
import traceback
#import AOImageView

import numpy as np
from PyQt5 import QtCore, QtWidgets, QtGui
from segmentation_models.backbones import backbones as smbb

from AOMetaList import *

if hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(__file__)
ICONS_DIR = os.path.join(BASE_DIR, 'Icons')
HELP_DIR = os.path.join(BASE_DIR, 'Help')
MODEL_WEIGHTS_DIR = os.path.join(BASE_DIR, 'model_weights')

def qt_icon(name):
    return QtGui.QIcon(os.path.join(ICONS_DIR, name))

def display_error(msg, msg2):
    b = QtWidgets.QMessageBox()
    b.setIcon(QtWidgets.QMessageBox.Critical)

    b.setText(msg)
    b.setInformativeText(msg2)
    b.setWindowTitle("Error")
    b.setDetailedText(traceback.format_exc())
    b.setStandardButtons(QtWidgets.QMessageBox.Ok)

    b.exec_()

def display_warning(msg, msg2):
    b = QtWidgets.QMessageBox()
    b.setIcon(QtWidgets.QMessageBox.Warning)

    b.setText(msg)
    b.setInformativeText(msg2)
    b.setWindowTitle("Warning")
    #b.setDetailedText(traceback.format_exc())
    b.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)

    return b.exec_()

def askYesNo(title, text, detail=None):
    b = QtWidgets.QMessageBox()
    b.setIcon(QtWidgets.QMessageBox.Question)
    b.setWindowTitle(title)
    b.setText(text)
    if detail:
         b.setInformativeText(detail)
    #
    b.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    b.setDefaultButton(QtWidgets.QMessageBox.Yes)
    #
    geom = QtWidgets.QApplication.primaryScreen().geometry()
    spacer = QtWidgets.QSpacerItem(geom.width()*20//100, 1,
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
    l = b.layout()
    l.addItem(spacer, l.rowCount(), 0, 1, l.columnCount())
    #
    return b.exec_() == QtWidgets.QMessageBox.Yes
#
class ao_progress_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ao_progress_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self._progressbar = None
        self._setup_layout()
        self.setWindowTitle('Show progress')

    def _setup_layout(self):
        self.setModal(True)
        hbox = QtWidgets.QHBoxLayout()
        self._progressbar = QtWidgets.QProgressBar()
        hbox.addWidget(self._progressbar)
        self.setLayout(hbox)

    def set_progress(self, val):
        self._progressbar.setValue(val)
        QtWidgets.QApplication.processEvents()
        
class ao_loc_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ao_loc_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        self._setup_layout()
    #
    def _setup_layout(self):
        self.setWindowTitle('Image Data Locations')
        view_layout = QtWidgets.QGridLayout()
        self.setLayout(view_layout)
        #
        self.img_lab = QtWidgets.QLabel('Image File:')
        view_layout.addWidget(self.img_lab, 0, 0)
        self.img_txt = QtWidgets.QLineEdit('')
        self.img_txt.setReadOnly(True)
        view_layout.addWidget(self.img_txt, 1, 0)

        local_lab = QtWidgets.QLabel('Annotations File (grayed if does not exist):')
        view_layout.addWidget(local_lab, 2, 0)
        self.local_txt = QtWidgets.QLineEdit('')
        self.local_txt.setReadOnly(True)
        view_layout.addWidget(self.local_txt, 3, 0)
        
        hist_lab = QtWidgets.QLabel('Auto-backup (History) File:')
        view_layout.addWidget(hist_lab, 4, 0)
        self.hist_txt = QtWidgets.QLineEdit('')
        self.hist_txt.setReadOnly(True)
        view_layout.addWidget(self.hist_txt, 5, 0)
        
        self.buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        self.buttonbox.accepted.connect(self.accept)
        view_layout.addWidget(self.buttonbox, 6, 0)
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    def setPaths(self, img, img_path, loc_path, hist_path):
        try:
            _ts = datetime.datetime.fromtimestamp(os.stat(img_path).st_mtime_ns * 0.000000001)
            ts = _ts.strftime('%m/%d/%Y %H:%M:%S.%f')[:-3]
        except Exception:
            ts = '--'
        img_info = 'Image File [%dx%d pix, last modified %s]:' % (img.GetWidth(), img.GetHeight(), ts)
        self.img_lab.setText(img_info)
        self.img_txt.setText(img_path)
        self.local_txt.setText(loc_path)
        pal = QtGui.QPalette()
        if not os.path.isfile(loc_path):
            pal.setColor(QtGui.QPalette.Text, QtGui.QColor(0xC0, 0xC0, 0xC0))
        self.local_txt.setPalette(pal)
        self.hist_txt.setText(hist_path)
    #

class ao_parameter_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ao_parameter_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.resize(geom.width()*36/100, geom.height()*60/100)
        #
        self._mute = False
        self._builtin_map = {}
        #
        self.normal = QtGui.QFont(self.font())
        self.bold = QtGui.QFont(self.normal)
        self.bold.setBold(True)
        #
        self._setup_layout()
        #
        self._update_builtin_weights()
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    def _setup_layout(self):
        self.setWindowTitle('RPE detection')
        
        ml_panel = QtWidgets.QGroupBox('Machine Learning Model Weights')
        ml_layout = QtWidgets.QGridLayout()
        ml_panel.setLayout(ml_layout)
        self.rb_builtin = QtWidgets.QRadioButton('Built-in:')
        ml_layout.addWidget(self.rb_builtin, 0, 0)
        
        self.cb_builtin = QtWidgets.QComboBox()
        ml_layout.addWidget(self.cb_builtin, 0, 1, 1, 2)
        
        self.rb_custom = QtWidgets.QRadioButton('Custom:')
        ml_layout.addWidget(self.rb_custom, 1, 0)
        self.txCustomWeights = QtWidgets.QLineEdit()
        self.txCustomWeights.setReadOnly(True)
        ml_layout.addWidget(self.txCustomWeights, 1, 1)
        self.btnBrowse = QtWidgets.QPushButton('Browse')
        ml_layout.addWidget(self.btnBrowse, 1, 2)
        self.rb_builtin.setChecked(True)
        
        bblist = ', '.join(sorted(smbb.backbones.keys()))
        ml_tip_lb = QtWidgets.QLabel('Note: Model Weights file name must be formatted as "*_<backbone>[_voronoi].h5"\n'+
            'Possible values for <backbone> are: '+bblist)
        ml_tip_lb.setStyleSheet('color: #333366')
        ml_layout.addWidget(ml_tip_lb, 2, 0, 1, 3)

        probability_label = QtWidgets.QLabel('Probability threshold:')
        self._probability_threshold_input = QtWidgets.QDoubleSpinBox()
        self._probability_threshold_input.setRange(0, 1)
        self._probability_threshold_input.setSingleStep(0.001)
        # self._probability_threshold_input.setValue(0.015)
        self._probability_threshold_input.setValue(0.5)
        self._probability_threshold_input.setDecimals(3)

        clustering_radius_label = QtWidgets.QLabel('Clustering radius:')
        self._clustering_radius_input = QtWidgets.QSpinBox()
        self._clustering_radius_input.setRange(1, 1000)
        self._clustering_radius_input.setSingleStep(1)
        self._clustering_radius_input.setValue(20)

        fov_label = QtWidgets.QLabel('Field of view:')
        self._fov_input = QtWidgets.QLineEdit('0.75')
        self._fov_input.setValidator(QtGui.QDoubleValidator(0.0, 10.0, 3))

        self.buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                          QtWidgets.QDialogButtonBox.Cancel)
        okBtn = self.buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        okBtn.setText('  Detect Checked  ')
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)

        self.imageTable = QtWidgets.QTableWidget(0, 2)
        self.imageTable.setColumnWidth(0, 8)
        self.imageTable.setHorizontalHeaderLabels([u'\u221A', u'Image File Name']);
        self.imageTable.horizontalHeader().setStretchLastSection(True)
        self.imageTable.verticalHeader().setVisible(False)
        self.imageTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);
        self.imageTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);
        self.imageTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);
        self.imageTable.setShowGrid(False);
        self.imageTable.horizontalHeader().sectionClicked.connect(self.OnHeaderClicked)

        view_layout = QtWidgets.QGridLayout()
        view_layout.setColumnStretch(0, 0)
        view_layout.setColumnStretch(1, 0)
        view_layout.setColumnStretch(2, 10)
        view_layout.addWidget(self.imageTable, 0, 0, 1, 3)

        view_layout.addWidget(ml_panel, 1, 0, 1, 3)
        
        view_layout.addWidget(probability_label, 2, 0)
        view_layout.addWidget(self._probability_threshold_input, 2, 1)
        view_layout.addWidget(clustering_radius_label, 3, 0)
        view_layout.addWidget(self._clustering_radius_input, 3, 1)
        view_layout.addWidget(fov_label, 4, 0)
        view_layout.addWidget(self._fov_input, 4, 1)
        
        self.defBtn = QtWidgets.QPushButton('Restore Defaults')
        view_layout.addWidget(self.defBtn, 5, 0)
        self.defBtn.clicked.connect(self.restoreDefaults)
        
        view_layout.addWidget(self.buttonbox, 6, 0, 1, 3)
        self.setLayout(view_layout)
        #
        self.btnBrowse.clicked.connect(self._on_browse_custom)
        self.rb_custom.toggled.connect(self._handle_custom_rb)
    #
    def restoreDefaults(self):
        self._mute = True
        self._probability_threshold_input.setValue(0.5)
        self._clustering_radius_input.setValue(20)
        self._fov_input.setText('0.75')
        try:
            self.cb_builtin.setCurrentIndex(0)
        except Exception:
            pass
        self.rb_builtin.setChecked(True)
        self._mute = False
    #
    def SetImageList(self, items):
        self.imageTable.setRowCount(len(items))
        for row, nm in enumerate(items):
            cb = QtWidgets.QCheckBox()
            cb.setContentsMargins(8, 2, 2, 0)
            self.imageTable.setCellWidget(row, 0, cb)
            self.imageTable.setItem(row, 1, QtWidgets.QTableWidgetItem(items[row]))
    #
    def SetCheckedRows(self, rows):
        for row in range(self.imageTable.rowCount()):
            self.imageTable.cellWidget(row, 0).setChecked(row in rows)
    def checkedRows(self):
        return [row for row in range(self.imageTable.rowCount()) \
            if self.imageTable.cellWidget(row, 0).isChecked()]
    #
    def SetHighlightedRow(self, h_row):
        for row in range(self.imageTable.rowCount()):
            self.imageTable.item(row, 1).setFont(self.bold if row==h_row else self.normal)
        if h_row >= 0 and h_row < self.imageTable.rowCount():
            self.imageTable.selectRow(h_row)
            self.imageTable.scrollToItem(self.imageTable.item(h_row, 1))
    #
    def OnHeaderClicked(self, col):
        if col != 0: return
        ck = len(self.checkedRows()) == 0
        for row in range(self.imageTable.rowCount()):
            self.imageTable.cellWidget(row, 0).setChecked(ck)
    #
    def accept(self):
        if len(self.checkedRows()) > 0:
            QtWidgets.QDialog.accept(self)
    #
    def _update_builtin_weights(self):
        cdir = MODEL_WEIGHTS_DIR
        self._builtin_map.clear()
        for fn in os.listdir(cdir):
            fpath = os.path.join(cdir, fn)
            if not os.path.isfile(fpath): continue
            bn, ext = os.path.splitext(fn)
            if ext.lower() == '.h5':
                self._builtin_map[bn] = fpath
        self.cb_builtin.clear()
        for method in sorted(self._builtin_map.keys()):
            self.cb_builtin.addItem(method)
    def update_builtin_weights(self):
        save_name = self.builtin_weights
        self._update_builtin_weights()
        self.builtin_weights = save_name
    #
    def _handle_custom_rb(self, st):
        if self._mute: return
        if self.custom:
            try:
                ok = os.path.isfile(self.custom_weights)
            except Exception:
                ok = False
            if not ok:
                self._browse_custom()
        self.cb_builtin.setEnabled(not self.custom)
    #
    def _on_browse_custom(self):
        self._mute = True
        self.custom = True
        self._mute = False
        self._browse_custom()
    #
    def _validate_custom(self):
        if self.custom and not self.custom_weights:
            self._mute = True
            self.custom = False
            self._mute = False
    #
    def _browse_custom(self):
        cdir = os.path.dirname(self.custom_weights) if self.custom_weights else QtCore.QDir.home()
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["Trained ML model weights (*.h5)"])
        file_dialog.selectNameFilter('')
        file_dialog.setWindowTitle('Browse Trained ML Model Weights')
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        file_dialog.setLabelText(QtWidgets.QFileDialog.Accept, 'Select')
        file_dialog.setDirectory(cdir)
        rc = file_dialog.exec_()
        if not rc:
            self._validate_custom()
            return
        flist = file_dialog.selectedFiles()
        if len(flist) < 1:
            self._validate_custom()
            return
        self.custom_weights = os.path.abspath(flist[0])
    #
    @property
    def custom(self):
        return self.rb_custom.isChecked()
    @custom.setter
    def custom(self, st):
        self.rb_builtin.setChecked(not st)
        self.cb_builtin.setEnabled(not st)
        self.rb_custom.setChecked(st)
    #
    @property
    def custom_weights(self):
        return self.txCustomWeights.text()
    @custom_weights.setter
    def custom_weights(self, v):
        self.txCustomWeights.setText(v)
        self.txCustomWeights.setToolTip(v)
    #
    @property
    def builtin_weights(self):
        return self.cb_builtin.currentText()
    @builtin_weights.setter
    def builtin_weights(self, v):
        if v in self._builtin_map:
            self.cb_builtin.setCurrentText(v)
    #
    @property
    def probablity_threshold(self):
        return self._probability_threshold_input.value()
    @probablity_threshold.setter
    def probablity_threshold(self, v):
        try:
            self._probability_threshold_input.setValue(float(v))
        except Exception:
            pass
    #
    @property
    def clustering_radius(self):
        return self._clustering_radius_input.value()
    @clustering_radius.setter
    def clustering_radius(self, v):
        try:
            self._clustering_radius_input.setValue(int(v))
        except Exception:
            pass
    #
    @property
    def image_fov(self):
        return float(self._fov_input.text())
    @image_fov.setter
    def image_fov(self, v):
        try:
            v = float(v)
            self._fov_input.setText(str(v))
        except Exception:
            pass
    #
    @property
    def model_weights(self):
        if self.custom:
            fpath = self.custom_weights
            if not fpath or not os.path.isfile(fpath):
                return None
            name, ext = os.path.splitext(os.path.basename(fpath))
            return name, fpath
        name = self.builtin_weights
        if name in self._builtin_map:
            return name, self._builtin_map[name]
        return None
    #
    STATE_ATTRIBUTES = ('custom', 'custom_weights', 'builtin_weights', 'probablity_threshold',
        'clustering_radius', 'image_fov',)
    @property
    def state(self):
        return dict([(a, getattr(self,a)) for a in self.STATE_ATTRIBUTES])
    @state.setter
    def state(self, jobj):
        self._mute = True
        for a in self.STATE_ATTRIBUTES:
            if a in jobj:
                setattr(self, a, jobj[a])
        if self.custom and self.model_weights is None:
            self.custom = False
        self._mute = False
    #

class _crossLabel(QtWidgets.QLabel):
    def __init__(self, callback=None):
        super(_crossLabel, self).__init__()
        self.callback = callback
        #
        self.margin = 10
        #
        self.setStyleSheet(f'margin: {self.margin} {self.margin} {self.margin} {self.margin};')
        self.setMouseTracking(True)
        #
        self.rangeX = (0, 1000)
        self.rangeY = (0, 1000)
        self.posX = 0
        self.posY = 0
        #
        img_data = np.empty(shape=(256, 256), dtype=np.float32)
        for c in range(256):
            img_data[0][c] = c
        row0 = img_data[0]
        for j in range(1,256):
            img_data[j] = row0 * ((255. - j * 0.85) / 255.) + (127.5 * j * 0.85 / 255.)
        img_data = np.transpose(img_data, (1,0)).copy()
        img = QtGui.QImage(img_data.astype(np.uint8), 256, 256, 256, QtGui.QImage.Format_Grayscale8)
        self.pixmap0 = QtGui.QPixmap.fromImage(img)
        self._updateScaledPixmap()
        #
    def _updateScaledPixmap(self):
        self.scpixmap = self.pixmap0.scaled(self.width()-self.margin*2, self.height()-self.margin*2, transformMode=QtCore.Qt.FastTransformation)
        self.setPixmap(self.scpixmap)
        #self.update()
    def resizeEvent(self, e):
        self._updateScaledPixmap()
    #
    def _handle_mouse_pos(self, e):
        pt = e.pos()
        x0 = self.margin
        x1 = self.width() - self.margin
        w = x1 - x0
        y0 = self.margin
        y1 = self.height() - self.margin
        h = y1 - y0
        x = (pt.x() - x0) * (self.rangeX[1] - self.rangeX[0]) / w + self.rangeX[0]
        y = (h - pt.y() + y0) * (self.rangeY[1] - self.rangeY[0]) / h + self.rangeY[0]
        if x>=self.rangeX[0] and x<=self.rangeX[1] and y>=self.rangeY[0] and y<=self.rangeY[1]:
            if self.callback:
                self.callback(int(x+0.5), int(y+0.5))
    #
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._handle_mouse_pos(e)
    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.LeftButton:
            self._handle_mouse_pos(e)
    #
    def paintEvent(self, e):
        super(_crossLabel, self).paintEvent(e)
        qp = QtGui.QPainter()
        qp.begin(self)
        pen = QtGui.QPen(QtCore.Qt.yellow, 2, QtCore.Qt.CustomDashLine)
        pen.setDashPattern([2, 4])
        qp.setPen(pen)
        #
        x0 = self.margin
        x1 = self.width() - self.margin
        w = x1 - x0
        y0 = self.margin
        y1 = self.height() - self.margin
        h = y1 - y0
        x = (self.posX - self.rangeX[0]) * w / (self.rangeX[1] - self.rangeX[0]) + x0
        qp.drawLine(x, y0, x, y1)
        y = h - (self.posY - self.rangeY[0]) * h / (self.rangeY[1] - self.rangeY[0]) + y0
        qp.drawLine(x0, y, x1, y)
        #
        qp.end()
    #

class ao_brightness_contrast(QtWidgets.QWidget):
    def __init__(self, mainwin, parent=None, callback=None):
        super(ao_brightness_contrast, self).__init__(parent)
        self.mainwin = mainwin
        self.callback = callback
        #
        self.manual = True
        #
        flags = self.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QtGui.QPalette.Shadow)
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        wsz = geom.height() * 20 // 100
        self.resize(wsz, wsz)
        self.move(30, 30)
        #
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(2)
        view_layout.setVerticalSpacing(2)
        self.setLayout(view_layout)
        #
        for idx, stretch in enumerate((0., 1., 0.)):
            view_layout.setColumnStretch(idx, stretch)
            view_layout.setRowStretch(idx, stretch)
        #
        b_lab = QtWidgets.QLabel('\u263C')
        b_lab.setFont(QtGui.QFont('Arial', 10))
        view_layout.addWidget(b_lab, 0, 0)
        c_lab = QtWidgets.QLabel(' \u25D1')
        c_lab.setFont(QtGui.QFont('Arial', 16))
        view_layout.addWidget(c_lab, 2, 2)
        #
        self.c_sl = sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        sl.setRange(0,1000)
        sl.setTickInterval(100)
        sl.setTickPosition(QtWidgets.QSlider.TicksAbove)
        view_layout.addWidget(sl, 2, 1)
        self.b_sl = sl = QtWidgets.QSlider(QtCore.Qt.Vertical)
        sl.setRange(0,1000)
        sl.setTickInterval(100)
        sl.setTickPosition(QtWidgets.QSlider.TicksRight)
        view_layout.addWidget(sl, 1, 0)
        self.crosslabel = _crossLabel(callback=self.onCrossLabel)
        view_layout.addWidget(self.crosslabel, 1, 1)
        self.rbtn = QtWidgets.QPushButton('\u2A01')
        self.rbtn.setStyleSheet('margin: 0; padding: 1 4 1 4;')
        self.rbtn.setBackgroundRole(QtGui.QPalette.Dark)
        view_layout.addWidget(self.rbtn, 2, 0)
        #
        self.c_sl.valueChanged.connect(self.onColorWindowSlider)
        self.b_sl.valueChanged.connect(self.onColorLevelSlider)
        self.rbtn.clicked.connect(lambda: self.onCrossLabel(500,500))
        #
        self.setMaximumSize(self.size())
        #
        self._mute = False
    #
    def onColorWindowSlider(self, v):
        self.crosslabel.posX = v
        self.crosslabel.update()
        if not self._mute and self.callback:
            self.callback(self.color_info)
    def onColorLevelSlider(self, v):
        self.crosslabel.posY = v
        self.crosslabel.update()
        if not self._mute and self.callback:
            self.callback(self.color_info)
    #
    def onCrossLabel(self, x, y):
        mute = self._mute
        self._mute = True
        self.b_sl.setValue(y)
        self.c_sl.setValue(x)
        self._mute = mute
        if not self._mute and self.callback:
            self.callback(self.color_info)
    #
    @property
    def color_info(self):
        y = self.b_sl.value()
        clvl = y * 767. / 1000. - 256. if y != 500 else 127.5
        x = self.c_sl.value()
        cwin = math.pow(x/125.1347,4.) + 0.1 if x != 500 else 255.
        return (clvl, cwin)
    @color_info.setter
    def color_info(self, v):
        try:
            clvl, cwin = v
            y = (clvl + 256.) * 1000. / 767.
            if y<0: y=0
            elif y>1000: y=1000
            if cwin <= 0.1: x=0
            else:
                x = math.pow((cwin-0.1), 0.25)*125.1347
                if x>1000: x=1000
            x = int(x)
            y = int(y)
        except Exception as ex:
            print(ex)
            x = y = 500
        self._mute = True
        self.onCrossLabel(x, y)
        self._mute = False
    #



class ao_source_window(QtWidgets.QWidget):
    def __init__(self, mainwin):
        super(ao_source_window, self).__init__(None)
        self.mainwin = mainwin
        self._mute = True
        #
        self.cmeta = MetaRecord(when=MetaRecord.TODAY, user=MetaRecord.CURRENT_USER)
        if self.mainwin:
            self.cmeta.realWho = self.mainwin.getRealName(self.cmeta.user)
        #
        flags = self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        #flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.gw = geom.width()
        self.gh = geom.height()
        self.resize(self.gw * 60 // 100, self.gh * 32 // 100)
        #
        self._contours = MetaList()
        self._setup_layout()
        self.sourceTable.setFocus()
        self._mute = False
        #
    #
    def _setup_layout(self):
        self.setWindowTitle('Annotation Sources')
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(8)
        view_layout.setVerticalSpacing(8)
        self.setLayout(view_layout)
        #
        name_layout = QtWidgets.QGridLayout()
        name_layout.setColumnStretch(0, 0)
        name_layout.setColumnStretch(1, 1)
        view_layout.addLayout(name_layout, 0, 0)
        nameLabel = QtWidgets.QLabel('Real User Name:')
        name_layout.addWidget(nameLabel, 0, 0)
        self.realNameTxt = QtWidgets.QLineEdit()
        name_layout.addWidget(self.realNameTxt, 0, 1)
        #
        self.sourceTable = QtWidgets.QTableWidget(0, 6)
        self.sourceTable.setColumnWidth(0, 8)
        self.sourceTable.setColumnWidth(1, 2)
        self.sourceTable.setColumnWidth(2, self.gw * 4 // 100)
        self.sourceTable.setColumnWidth(3, self.gw * 5 // 100)
        self.sourceTable.setColumnWidth(4, self.gw * 8 // 100)
        self.sourceTable.setHorizontalHeaderLabels([u'\u221A', u'', u'Count', u'Date', u'User', u'Comment']);
        self.sourceTable.horizontalHeader().setStretchLastSection(True)
        self.sourceTable.verticalHeader().setVisible(False)
        #self.sourceTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);
        self.sourceTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);
        self.sourceTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);
        self.sourceTable.setShowGrid(False);
        self.sourceTable.horizontalHeader().sectionClicked.connect(self.OnHeaderClicked)
        view_layout.addWidget(self.sourceTable, 1, 0)
        #
        btn_layout = QtWidgets.QGridLayout()
        btn_layout.setColumnStretch(0, 0)
        btn_layout.setColumnStretch(1, 0)
        btn_layout.setColumnStretch(2, 1)
        btn_layout.setColumnStretch(3, 0)
        btn_layout.setHorizontalSpacing(16)
        view_layout.addLayout(btn_layout, 2, 0)
        self.newButton = QtWidgets.QPushButton('New')
        btn_layout.addWidget(self.newButton, 0, 0)
        self.delButton = QtWidgets.QPushButton('Delete')
        btn_layout.addWidget(self.delButton, 0, 1)
        self.dfltButton = QtWidgets.QPushButton('Default')
        btn_layout.addWidget(self.dfltButton, 0, 3)
        #
        self.realNameTxt.setText(self.cmeta.realWho)
        self.realNameTxt.editingFinished.connect(self.onRealNameChanged)
        self.sourceTable.cellChanged.connect(self.onDescriptionChanged)
        self.sourceTable.currentCellChanged.connect(self.onCurrentCellChange)
        self.newButton.clicked.connect(self.onNewButton)
        self.delButton.clicked.connect(self.onDelButton)
        self.dfltButton.clicked.connect(self.onDefaultButton)
    #
    def onRealNameChanged(self):
        self.cmeta.realWho = self.realNameTxt.text()
        MetaRecord.REAL_USER = self.cmeta.realUser if 'realUser' in self.cmeta.__dict__ else None
        for meta, lst in self._contours.itermapping():
            if meta.userkey == MetaRecord.current_key():
                meta.realWho = self.cmeta.realWho
        self.setMetaList(self._contours)
        if self.mainwin:
            self.mainwin.setRealName(self.cmeta.realWho)
    #
    def onDescriptionChanged(self, row, col):
        if self._mute: return
        if col != 5: return
        try:
            comment = self.sourceTable.item(row, col).text().strip()
            mrec = self._meta_list[row][0]
            if comment:
                mrec.__dict__['comment'] = comment
            else:
                if 'comment' in mrec.__dict__:
                    del mrec.comment
            self._update_defaults()
        except Exception:
            pass
    #
    def OnHeaderClicked(self, col):
        if col != 0: return
        self._mute = True
        ck = False
        for row in range(self.sourceTable.rowCount()):
            if not self.sourceTable.cellWidget(row, 0).isChecked():
                ck = True
                break
        for row in range(self.sourceTable.rowCount()):
            self.sourceTable.cellWidget(row, 0).setChecked(ck)
        self._mute = False
        self._update_selection(False)
    #
    def _update_selection(self, st):
        if self._mute or not hasattr(self._contours, 'setGrayMeta'):
            return
        grayed = []
        for cb, (meta, cnt) in zip(self._cb_list, self._meta_list):
            if not cb.isChecked():
                grayed.append(meta)
        self._contours.setGrayMeta(grayed)
        if self.mainwin:
            self._mute = True
            self.mainwin._update_sources()
            self._mute = False
    #
    def _update_button_status(self):
        curmeta = self._current_meta()
        self.delButton.setEnabled(self._contours.meta.can_delete_meta(curmeta))
        self.dfltButton.setEnabled(self._can_be_default(curmeta))
    #
    def onCurrentCellChange(self, row, col, prow, pcol):
        if self._mute: return
        self._mute = True
        if col != 5:
            self.sourceTable.setCurrentCell(row, 5)
        meta = self._current_meta()
        if self._can_be_default(meta):
            self._contours.meta.default = meta
            if self.mainwin:
                self.mainwin._set_annotations(None)
        self._mute = False
        self._update_button_status()
    #
    def setMetaList(self, contours, cur_row=-1):
        if self._mute: return
        self._mute = True
        cur_col = -1
        if contours is self._contours:
            if cur_row < 0:
                cur_row = self.sourceTable.currentRow()
            cur_col = 5
        self._contours = contours
        self._meta_list = []
        self._cb_list = []
        for attr in ('meta', 'itermapping', 'isGrayMetaRec'):
            if not hasattr(self._contours, attr):
                self.sourceTable.setRowCount(0)
                return
        #
        for meta, lst in self._contours.itermapping():
            self._meta_list.append((meta, len(lst)))
        self.sourceTable.setRowCount(len(self._meta_list))
        #
        for row, (meta, cnt) in enumerate(self._meta_list):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(not contours.isGrayMetaRec(meta))
            cb.setContentsMargins(8, 2, 2, 0)
            self.sourceTable.setCellWidget(row, 0, cb)
            cb.toggled.connect(self._update_selection)
            self._cb_list.append(cb)
            item = QtWidgets.QTableWidgetItem('')
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 1, item)
            item = QtWidgets.QTableWidgetItem(f'{cnt}   ')
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter);
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 2, item)
            item = QtWidgets.QTableWidgetItem(meta.when)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 3, item)
            item = QtWidgets.QTableWidgetItem(meta.realWho)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 4, item)
            item = QtWidgets.QTableWidgetItem(meta.description)
            if meta.userkey != MetaRecord.current_key():
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            else:
                hi = 0xF0 if row&1 == 0 else 0xF8
                item.setBackground(QtGui.QBrush(QtGui.QColor(hi, hi, 0xFF)))
                item.setForeground(QtGui.QBrush(QtGui.QColor(0, 0, 0x55)))
            self.sourceTable.setItem(row, 5, item)
        #
        self.sourceTable.clearSelection()
        self.sourceTable.setCurrentCell(cur_row, cur_col)
        self._update_defaults()
        self._mute = False
    #
    def onNewButton(self):
        self.sourceTable.setFocus()
        self._mute = True
        meta = MetaRecord(user=MetaRecord.CURRENT_USER)
        self._contours.meta.addmeta(meta, newid=True, setdefault=True)
        if self.mainwin:
            self.mainwin._set_annotations(None)
        self._mute = False
        self.setMetaList(self._contours, cur_row=0)
    #
    def onDelButton(self):
        self.sourceTable.setFocus()
        meta = self._current_meta()
        if not self._contours.meta.can_delete_meta(meta):
            return
        self._mute = True
        self._contours.meta.delmeta(meta)
        if self.mainwin:
            self.mainwin._set_annotations(None)
        self._mute = False
        self.setMetaList(self._contours, cur_row=0)
    #
    def _can_be_default(self, meta):
        if meta is None: return False
        return meta.userkey == MetaRecord.current_key()
    #
    def _update_defaults(self):
        has_default = False
        self._mute = True
        for row, (meta, cnt) in enumerate(self._meta_list):
            st = ''
            if MetaRecord.COMMENT and self._can_be_default(meta) and not 'comment' in meta.__dict__:
                self.sourceTable.item(row, 5).setText(MetaRecord.COMMENT)
                if not has_default:
                    st = '*'
                    has_default = True
            self.sourceTable.item(row, 1).setText(st)
        self._mute = False
        self._update_button_status()
    #
    def _current_meta(self):
        try:
            return self._meta_list[self.sourceTable.currentRow()][0]
        except Exception:
            return None
    #
    def onDefaultButton(self):
        self.sourceTable.setFocus()
        meta = self._current_meta()
        if not self._can_be_default(meta):
            return
        #
        if MetaRecord.COMMENT:
            for _meta, cnt in self._meta_list:
                if _meta.userkey == meta.userkey and not 'comment' in _meta.__dict__:
                    _meta.__dict__['comment'] = MetaRecord.COMMENT
        #
        row = self.sourceTable.currentRow()
        if self.sourceTable.item(row, 1).text() == '*':
            MetaRecord.COMMENT = None
        else:
            txt = self.sourceTable.item(row, 5).text().strip()
            if not txt:
                txt = None
            MetaRecord.COMMENT = txt
            if 'comment' in meta.__dict__:
                del meta.__dict__['comment']
        self._update_defaults()
    #

