__all__ = ('BASE_DIR', 'ICONS_DIR', 'HELP_DIR', 'qt_icon', 'display_error', 'display_warning', 'askYesNo',
        'ao_progress_dialog', 'ao_loc_dialog', 'ao_parameter_dialog',)

import os
import sys
import time
import datetime
import traceback
import AOImageView

from PyQt5 import QtCore, QtWidgets, QtGui
from segmentation_models.backbones import backbones as smbb

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
