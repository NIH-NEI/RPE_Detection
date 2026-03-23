from __future__ import division
import os, sys
import json
import math
from collections import defaultdict
from enum import Enum
import vtk

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
# import matplotlib.pyplot as plt
import SimpleITK as sitk

import numpy as np
from keras.preprocessing.image import load_img
from AOMetaList import *
import AOImageView
from AOImageView import MouseOp
import AOFileIO
import AOMethod
from AOSettingsDialog import *
from AODisplay import ao_display_settings
from AOSnap import ao_snap_dialog
from AOHotKey import ao_hotkey_dialog
import AOConfig as cfg

IMG_ICON_2D = 0
IMG_ICON_ANN = 1
IMG_ICON_3D = 2
IMG_ICON_OPEN = 4

_big_icon = QtCore.QUrl.fromLocalFile(os.path.join(ICONS_DIR, 'RPE_Detection256x256.png'))
about_html = '''
<table><tr>
<td><img src="%s">&nbsp;&nbsp;</td>
<td><b>%s %s</b><div>
<a href="https://nei.nih.gov/intramural/translational-imaging">Tam lab</a><br>
<a href="https://nei.nih.gov/">National Eye Institute</a><br>
<a href="https://www.nih.gov/">National Institutes of Health</a></div><div><br>
<span style="color:#000088;">RPE Detection (Machine Learning edition).</span><br>
If any portion of this software is used, please<br>
cite the following paper in your publication:<br>
</td></tr><tr><td colspan=2>
<b>Jianfei Liu, Yoo-Jean Han, Tao Liu, Nancy Aguilera, and Johnny Tam,</b> <br>
"Spatially Aware Dense-LinkNet Based Regression Improves Fluorescent <br>
Cell Detection in Adaptive Optics Ophthalmic Images,"<br>
<i>IEEE Journal of Biomedical Health Informatics</i> 24(12):3520-3528, 2020</td></tr></table>
''' % (_big_icon.url(), cfg.APP_NAME, cfg.APP_VERSION)


#
class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        #self.setSizeGripEnabled(True)
        self.setWindowIcon(qt_icon('about.png'))
        self.setWindowTitle('About '+cfg.APP_NAME)
        #
        layout = QtWidgets.QVBoxLayout()
        lbl = QtWidgets.QLabel(about_html)
        lbl.setTextFormat(QtCore.Qt.RichText)
        lbl.setOpenExternalLinks(True)
        #
        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        #
        layout.addWidget(lbl)
        layout.addWidget(buttonbox)
        self.setLayout(layout)
#

class InputImageData(object):
    def __init__(self, img_fpath, itk_img, flat=True):
        self.itk_img = itk_img
        self.filepath = img_fpath
        self._name = os.path.splitext(os.path.basename(self.filepath))[0]
        self.color = (127.5, 255.)
        self.flat = flat
        #
        self.imgsz = self.itk_img.GetSize()
        self.ndim = len(self.imgsz)
        self.nframes = 1 if self.ndim == 2 else self.imgsz[2]
        self._cframe = 0
        self.all_annotations = [None for _ in range(self.nframes)]
        self._unchecked = set()
        #
        self.local_apath = None
        self.hist_apath = None
    #
    @property
    def name(self):
        return self._name
    @property
    def listname(self):
        return self._name if self.ndim==2 else f'[{self.nframes}] {self._name}'
    @property
    def statusname(self):
        parts = []
        if self.ndim == 3:
            parts.append(f'Frame {self.cframe+1} of {self.nframes}')
        sz = self.GetSize()
        parts.append(f'[{sz[0]}x{sz[1]}]')
        parts.append(self._name)
        if self.is_annotated:
            parts.append('(Annotated)')
        return ' '.join(parts)
    @property
    def titlename(self):
        if self.nframes > 1:
            return f'[{self.cframe}] {self._name}'
        return self._name
    # @property
    # def listName(self):
    #     bn = self._name if self.ndim==2 else f'[{self.nframes}] {self._name}'
    #     if self.is_annotated:
    #         return u'\u221A'+bn
    #     return u' '+bn
    #
    @property
    def cframe(self):
        return self._cframe
    @cframe.setter
    def cframe(self, v):
        try:
            if v < 0: v = 0
            elif v >= self.nframes: v = self.nframes - 1
        except Exception:
            v = 0
        self._cframe = v
    #
    @property
    def annotations(self):
        fr = 0 if self.flat else self.cframe
        ann = self.all_annotations[fr]
        if ann is None:
            ann = self.all_annotations[fr] = MetaList()
        return ann
    @annotations.setter
    def annotations(self, v):
        fr = 0 if self.flat else self.cframe
        self.all_annotations[fr] = v
    #
    @property
    def is_annotated(self):
        return os.path.isfile(self.local_apath)
    #
    def GetNdArray(self):
        n_array = sitk.GetArrayFromImage(self.itk_img)
        return n_array[self.cframe] if self.ndim == 3 else n_array
    def GetOrigin(self):
        orig = self.itk_img.GetOrigin()
        return orig[:2] if self.ndim == 3 else orig
    def GetSize(self):
        return self.imgsz[:2] if self.ndim == 3 else self.imgsz
    def GetSpacing(self):
        spacing = self.itk_img.GetSpacing()
        return spacing[:2] if self.ndim == 3 else spacing
    #
    def isChecked(self, fr):
        return not fr in self._unchecked
    def setChecked(self, fr, st):
        if fr < 0 or fr >= self.nframes:
            return
        if not st:
            self._unchecked.add(fr)
        else:
            self._unchecked.discard(fr)
    def anyChecked(self):
        return len(self._unchecked) < self.nframes
    #
    def countChecked(self):
        return self.nframes - len(self._unchecked)
    #
    def importAnnotations(self, aa):
        for fr, _ in enumerate(self.all_annotations):
            ann = aa.get(fr)
            if isinstance(ann, tuple):
                ann = list(ann)
            if self.flat:
                if not self.all_annotations[0]:
                    self.all_annotations[0] = ann
                else:
                    self.add_all(self.all_annotations[0], ann)
            else:
                self.all_annotations[fr] = ann
        if 'unchecked' in aa:
            self._unchecked.clear()
            for fr in aa['unchecked']:
                self._unchecked.add(fr)
        #
        for mc in self.all_annotations:
            if not mc is None:
                mc.meta.addmeta(MetaRecord(), setdefault=True)
    #
    def exportAnnotations(self):
        res = {}
        for fr, ann in enumerate(self.all_annotations):
            if not ann is None:
                res[fr] = ann
        if len(self._unchecked) > 0:
            res['unchecked'] = sorted(self._unchecked)
        return res
    #
    def acount(self):
        res = 0
        for ann in self.all_annotations:
            if ann:
                res += len(ann)
        return res
    #
    def aclear(self):
        self.all_annotations = [None for _ in range(self.nframes)]
    #
    @staticmethod
    def pt_dist(pt1, pt2):
        return math.sqrt((pt1[0]-pt2[0])**2 + (pt1[1]-pt2[1])**2)
    #
    @staticmethod
    def can_add(annotations, addpt):
        for pt in annotations:
            if InputImageData.pt_dist(pt, addpt) < cfg.MARKER_TOLERANCE:
                return False
        return True
    #
    @staticmethod
    def add_all(annotations, addanns):
        if not addanns: return
        for addpt in addanns:
            if InputImageData.can_add(annotations, addpt):
                annotations.append(addpt)
    #

class EnterListWidget(QtWidgets.QListWidget):
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Enter or event.key() == QtCore.Qt.Key_Return:
            if self.currentItem():
                self.itemDoubleClicked.emit(self.currentItem())
        elif event.key() == QtCore.Qt.Key_Left:
            if self.currentRow() > 0:
                self.setCurrentRow(self.currentRow() - 1)
        elif event.key() == QtCore.Qt.Key_Right:
            if self.currentRow() < self.count() - 1:
                self.setCurrentRow(self.currentRow() + 1)
        else:
            super().keyPressEvent(event)
#

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.setWindowIcon(qt_icon('RPE_Detection.png'))

        cfg.main_wnd = self

        self._mute = True
        self._input_data = []
        self._cur_img_id = -1
        self._cur_3d = None
        self._status_id = -1

        self._icon_map = dict([
            (IMG_ICON_2D, qt_icon('circlegray')),
            (IMG_ICON_2D | IMG_ICON_ANN, qt_icon('circlegreen')),
            (IMG_ICON_3D, qt_icon('squareplusgray')),
            (IMG_ICON_3D | IMG_ICON_ANN, qt_icon('squareplusgreen')),
            (IMG_ICON_OPEN, qt_icon('squareminus')),
            (IMG_ICON_OPEN | IMG_ICON_ANN, qt_icon('squareminus'))
        ])

        self.loadDir = QtCore.QDir.home()
        self.saveDir = QtCore.QDir.home()
        self.realNameMap = {}

        # State dir/file
        self.state_dir = os.path.join(os.path.expanduser('~'), '.RPE_Detection')
        if not os.path.exists(self.state_dir):
            os.mkdir(self.state_dir)
        self.state_file = os.path.join(self.state_dir, 'state.json')
        self.shortcuts_file = os.path.join(self.state_dir, 'shortcuts.json')

        # create backup directory
        self.hist = cfg.HistoryManager(self.state_dir, suffix='.csv', retention_days=365)

        self._mouse_status = MouseOp.Normal

        self.setWindowTitle(cfg.APP_NAME+' ver. '+cfg.APP_VERSION)
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.setMinimumSize(geom.width()*60//100, geom.height()*2//3)

        self.resize(geom.width()*70//100, geom.height()*70//100)
        self.move(geom.width()*10//100, geom.height()*10//100)

        self._setup_layout()
        self._setup_menu()
        self._setup_toolbar()

        self._status_bar = QtWidgets.QStatusBar()
        self._status_bar.setStyleSheet("QStatusBar{border-top: 1px outset grey;}")
        self.setStatusBar(self._status_bar)

        self.mposText = QtWidgets.QLabel()
        #self.mposText.setReadOnly(True)
        self.mposText.setMaximumWidth(geom.width()*50//100)
        self._status_bar.addPermanentWidget(self.mposText, 0)

        self._detection_para_dlg = ao_parameter_dialog(self)
        self._detection_para_dlg.setMinimumSize(geom.width()/5, geom.height()/3)
        self._display_settings_dlg = ao_display_settings(None, contour_settings=False)
        self._display_settings_dlg.changed.connect(self._on_display_settings)
        self._progress_dlg = ao_progress_dialog(self)
        self._progress_dlg.setMinimumWidth(geom.width()/5)
        self._file_io = AOFileIO.ao_fileIO()
        self._detection = AOMethod.ao_method()
        self._data_loc_dlg = ao_loc_dialog(self)
        self._data_loc_dlg.setMinimumWidth(geom.width()/2)

        self._action_map = self.actionMap()
        self._default_key_map = self.hotkeys
        #
        self.status('Press F1 for help.')
        self.loadState()
        self.loadShortcuts()
        self.setAcceptDrops(True)
        self._mute = False
    #
    def keyReleaseEvent(self, e):
        if e.key() in (Qt.Qt.Key_Alt, Qt.Qt.Key_AltGr):
            while QtWidgets.QApplication.overrideCursor():
                QtWidgets.QApplication.restoreOverrideCursor()
            self._image_view.alt_reset()
    #
    def status(self, msg, temp=False):
        if temp:
            self.mposText.setText(msg)
        else:
            self._status_bar.showMessage(msg)
    #
    def actionMap(self):
        actmap = {}
        for onm in dir(self):
            if not hasattr(self, onm) or onm.startswith('__') or onm.startswith('_h_'): continue
            act = getattr(self, onm)
            if not isinstance(act, QtWidgets.QAction): continue
            ks = act.shortcut().toString()
            if ks:
                actmap[act.text()] = act
        return actmap
    #
    @property
    def hotkeys(self):
        res = {}
        for act_name, act in self._action_map.items():
            res[act_name] = act.shortcut().toString()
        return res
    @hotkeys.setter
    def hotkeys(self, key_map):
        for act_name, act in self._action_map.items():
            keystr = key_map.get(act_name, '')
            descr = act.statusTip() or act.toolTip()
            if not descr:
                descr = ''
            else:
                descr = descr.split('[')[0].strip()
            act.setShortcut(QtGui.QKeySequence(keystr))
            if descr and keystr:
                descr = f'{descr} [{keystr}]'
                act.setStatusTip(descr)
                act.setToolTip(descr)
    #
    def loadState(self):
        try:
            with open(self.state_file, 'r') as fi:
                jobj = json.load(fi)
            if 'displaySettings' in jobj:
                self._image_view.displaySettings = jobj['displaySettings']
            self._detection_para_dlg.state = jobj['detection_para']
            if 'loadDir' in jobj:
                self.loadDir = QtCore.QDir(jobj['loadDir'])
            if 'saveDir' in jobj:
                self.saveDir = QtCore.QDir(jobj['saveDir'])
            if 'realNameMap' in jobj:
                for usern, realn in jobj['realNameMap'].items():
                    self.realNameMap[usern] = realn
        except Exception:
            pass
        usern = self.getUserName()
        if usern in self.realNameMap:
            realn = self.realNameMap[usern]
            if realn and realn != usern:
                MetaRecord.REAL_USER = self.getRealName()
        self.save_ok = True
    def saveState(self):
        if not hasattr(self, 'save_ok'): return
        try:
            ldir = self.loadDir.canonicalPath()
        except Exception:
            ldir = None
        try:
            sdir = self.saveDir.canonicalPath()
        except Exception:
            sdir = None
        try:
            jobj = {
                'detection_para': self._detection_para_dlg.state,
                'displaySettings': self._image_view.displaySettings,
                'realNameMap': self.realNameMap,
            }
            if not ldir is None:
                jobj['loadDir'] = ldir
            if not sdir is None:
                jobj['saveDir'] = sdir
            with open(self.state_file, 'w') as fo:
                json.dump(jobj, fo, indent=2)
        except Exception:
            pass
    #
    def loadShortcuts(self):
        try:
            with open(self.shortcuts_file, 'r') as fi:
                hotkeys = json.load(fi)
                if hotkeys:
                    self.hotkeys = hotkeys
        except Exception:
            pass
    def saveShortcuts(self):
        try:
            with open(self.shortcuts_file, 'w') as fo:
                json.dump(self.hotkeys, fo, indent=2)
        except Exception:
            pass
    #
    def getUserName(self):
        return os.getenv('USERNAME', '=Anonymous=')
    def getRealName(self, usern=None):
        if usern is None:
            usern = self.getUserName()
        if usern in self.realNameMap:
            return self.realNameMap[usern]
        return usern
    def setRealName(self, realn):
        usern = os.getenv('USERNAME', '=Anonymous=')
        if realn and realn != usern:
            self.realNameMap[usern] = realn
        else:
            if usern in self.realNameMap:
                del self.realNameMap[usern]
        self.saveState()
    #
    def closeEvent(self, e):
        for winname in ('helpWindow', 'srcwin', '_display_settings_dlg'):
            if hasattr(self, winname):
                getattr(self, winname).close()
        self.saveState()
        e.accept()
    #
    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    def dropEvent(self, e):
        flist = cfg.InputList([url.toLocalFile() for url in e.mimeData().urls()])
        img_filenames = flist.get_files(('.tif', '.tiff'))
        csv_filenames = flist.get_files('.csv')
        strict = False
        if len(img_filenames) > 0:
            self._open_image_list(img_filenames, True)
            strict = True
        if len(csv_filenames) > 0:
            self._open_annotation_list(csv_filenames, strict)
    #
    def _initialize_input_data(self):
        self._input_data = []
        self._cur_img_id = -1
        self._cur_3d = None
    #
    def _setup_layout(self):
        frame = Qt.QFrame()
        self._file_list = EnterListWidget(self) #QtWidgets.QListWidget(self)
        self._file_list.currentRowChanged.connect(self._file_list_row_changed)
        self._file_list.itemDoubleClicked.connect(self._file_list_item_doublecklicked)
        self._file_list.itemChanged.connect(self._file_list_item_changed)

        self.vtkFrame = vtkWidget = QVTKRenderWindowInteractor(frame)
        self._image_view = AOImageView.ao_visualization(vtkWidget, parent=self, auto_tolerance=False)

        flist_layout = Qt.QVBoxLayout()
        flist_layout.addWidget(self._file_list, 4)

        view_layout = Qt.QGridLayout()
        view_layout.addWidget(vtkWidget, 0, 0)
        view_layout.addLayout(flist_layout, 0, 1, QtCore.Qt.AlignRight)
        view_layout.setColumnStretch(0, 5)
        view_layout.setColumnStretch(1, 1)

        frame.setLayout(view_layout)
        self.setCentralWidget(frame)
        self.show()

    def _setup_menu(self):
        self.open_image_act = QtWidgets.QAction('Open...', self, shortcut=QtGui.QKeySequence.Open,
                    icon=qt_icon('open'),
                    statusTip='Open RPE images/annotations',
                    toolTip='Open RPE images/annotations',
                    triggered=self._open_images)

        self.open_annotation_act = QtWidgets.QAction('Points...', self, shortcut='Ctrl+P',
                    icon=qt_icon('open_document1'),
                    statusTip='Open RPE annotations',
                    toolTip='Open RPE annotations',
                    triggered=self._open_annotations)

        self.save_data_act = QtWidgets.QAction('Save...', self, shortcut=QtGui.QKeySequence.Save,
                    icon=qt_icon('save'),
                    statusTip='Save RPE annotations',
                    toolTip='Save RPE annotations',
                    triggered=self._save_data)

        self.save_stats_act = QtWidgets.QAction('Export Annotation Stats...', self,
                    toolTip='Export Statistics from the Annotation Tracking system',
                    triggered=self._save_stats)

        self.delete_all_act = QtWidgets.QAction('Delete Annotations', self,
                    statusTip='Delete all RPE annotations on current image', triggered=self._delete_all)

        self.quit = QtWidgets.QAction('Exit', self, shortcut=QtGui.QKeySequence.Quit,
                    statusTip="Quit the application",
                    triggered=self._quit)

        self.toggle_visibility = QtWidgets.QAction('Annotation Visibility', self, shortcut='F2',
                    iconText='Show', icon=qt_icon('fovea'),
                    checkable=True, checked=True,
                    statusTip='Show/Hide all annotations [F2]',
                    toolTip='Show/Hide all annotations [F2]',
                    triggered=self._toggle_visibility)

        self.voronoi_act = QtWidgets.QAction('Voronoi', shortcut='Ctrl+V',
                icon=qt_icon('Voronoi'), statusTip='Toggle Voronoi Diagram display [Ctrl+V]',
                checkable=True, checked=False,
                triggered=self._toggle_voronoi)

        self.toggle_interpolation = QtWidgets.QAction('Image Interpolation', self, shortcut='Ctrl+I',
                    checkable=True, checked=True,
                    statusTip='Toggle Image Scale Pixel Interpolation [Ctrl+I]',
                    triggered=self._toggle_interpolation)

        self.reset_brightness_contrast = QtWidgets.QAction('Reset Image View', self, shortcut='F10',
                    statusTip='Reset Image View to the original size, position, brightness/contrast, etc.',
                    triggered=self._reset_brightness_contrast)

        self.bc_act = QtWidgets.QAction('Brightness/Contrast...', shortcut='F3',
                statusTip='Toggle Brightness/Contrast Window [F3]',
                checkable=True, checked=False,
                triggered=self._toggle_brightness_contrast)

        self.disp_act = QtWidgets.QAction('Display Settings...', iconText='Settings', shortcut='F5',
                icon=qt_icon('settings'), toolTip='Change Display Settings [F5]',
                triggered=self._show_display_settings)

        self.data_loc_act = QtWidgets.QAction('Show data file locations', self, shortcut='Ctrl+L',
                    statusTip='Show data locations of the current image file',
                    triggered=self._show_data_locations)

        self.meta_act = QtWidgets.QAction('Annotation Sources...', shortcut='F6',
                toolTip='Highlight select annotation sources [F6]',
                triggered=self._select_annotation_sources)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_image_act)
        file_menu.addAction(self.open_annotation_act)
        file_menu.addAction(self.save_data_act)
        file_menu.addAction(self.save_stats_act)
        file_menu.addSeparator()
        file_menu.addAction(self.delete_all_act)
        file_menu.addSeparator()
        file_menu.addAction(self.quit)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.toggle_visibility)
        view_menu.addAction(self.voronoi_act)
        view_menu.addAction(self.toggle_interpolation)
        view_menu.addSeparator()
        view_menu.addAction(self.bc_act)
        view_menu.addAction(self.data_loc_act)
        view_menu.addAction(self.meta_act)
        view_menu.addSeparator()
        view_menu.addAction(self.reset_brightness_contrast)
        view_menu.addSeparator()

        self.snap_annotated_act = QtWidgets.QAction('Snapshot...', self, shortcut='F7',
                    icon=qt_icon('camera'),
                    statusTip='Take a snapshot of the current image with annotations [F7]',
                    toolTip='Take a snapshot of the current image with annotations [F7]',
                    triggered=self._snap_annotated)
        view_menu.addAction(self.snap_annotated_act)

        self.screen_act = QtWidgets.QAction('Screenshot', self, shortcut='Ctrl+F7',
                    statusTip='Copy screenshot to clipboard [Ctrl+F7]',
                    toolTip='Copy screenshot to clipboard [Ctrl+F7]',
                    triggered=self._screen)
        view_menu.addAction(self.screen_act)

        opt_menu = self.menuBar().addMenu("&Options")
        self.hotkey_act = QtWidgets.QAction('Customize Keyboard Shortcuts...',
                statusTip='Select user-defined keyboard shortcuts for common actions',
                triggered=self._on_hotkey_act)
        opt_menu.addAction(self.hotkey_act)

        self.about_act = QtWidgets.QAction('About', self,
                    icon=qt_icon('about'),
                    triggered=self._display_about)
        self.help_act = QtWidgets.QAction('Help on controls...', self, shortcut='F1',
                    icon=qt_icon('help'),
                    toolTip='Display list of keyboard shortcuts',
                    statusTip='Display list of keyboard shortcuts',
                    triggered=self._display_help)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_act)
        help_menu.addAction(self.help_act)
    #
    def _screen(self):
        orig = self.vtkFrame.mapToGlobal(QtCore.QPoint(0,0))
        sz = self.vtkFrame.size()
        rect = QtCore.QRect(orig, sz)
        pixmap = QtWidgets.QApplication.primaryScreen().grabWindow(0)
        pixmap = pixmap.copy(rect)
        #
        clip = QtWidgets.QApplication.clipboard()
        clip.setPixmap(pixmap)
        self._status_bar.showMessage('Viewport copied to clipboard.')
    #
    def _update_listwidget(self, newlist=True):
        if not self._cur_3d is None:
            imdat = self._cur_3d
            nitems = imdat.nframes + 1
            if nitems != self._file_list.count():
                newlist = True
            self._mute = True
            if newlist:
                self._file_list.clear()
                item = QtWidgets.QListWidgetItem(self._icon_map[IMG_ICON_OPEN], imdat.name, self._file_list)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if imdat.anyChecked() else QtCore.Qt.Unchecked)
                font = item.font()
                hfont = QtGui.QFont(font.family(), font.pointSize(), QtGui.QFont.Bold)
                item.setFont(hfont)
                for i in range(imdat.nframes):
                    item = QtWidgets.QListWidgetItem(f'Frame {i+1}', self._file_list)
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            for i in range(imdat.nframes):
                item = self._file_list.item(i+1)
                item.setCheckState(QtCore.Qt.Checked if imdat.isChecked(i) else QtCore.Qt.Unchecked)
            self._mute = False
            return
        if len(self._input_data) != self._file_list.count():
            newlist = True
        if newlist:
            self._file_list.clear()
            for imdat in self._input_data:
                ico_idx = IMG_ICON_3D if imdat.nframes > 1 else IMG_ICON_2D
                if imdat.is_annotated:
                    ico_idx |= IMG_ICON_ANN
                QtWidgets.QListWidgetItem(self._icon_map[ico_idx], imdat.listname, self._file_list)
                #self._file_list.addItem(imdat.listName)
        else:
            for row, imdat in enumerate(self._input_data):
                self._file_list.item(row).setText(imdat.listname)

    def _setup_toolbar(self):
        settings_bar = self.addToolBar("Settings")
        settings_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        settings_bar.addAction(self.open_image_act)
        settings_bar.addAction(self.open_annotation_act)
        settings_bar.addAction(self.save_data_act)

        settings_bar.addSeparator()

        # Mouse Op button group
        mouse_group = QtWidgets.QActionGroup(self)
        self.default_act = QtWidgets.QAction('Adjust', mouse_group, shortcut='Ctrl+M',
                icon=qt_icon('mouse'), toolTip='Default Mouse Mode - adjust brightness/contrast [Ctrl+M]',
                checkable=True, checked=True,
                triggered=lambda: self._set_mouse_mode(MouseOp.Normal))
        settings_bar.addAction(self.default_act)
        self.add_act = QtWidgets.QAction('Add', mouse_group, shortcut='Ctrl+C',
                icon=qt_icon('draw_point'), toolTip='Mouse click adds a marker [Ctrl+C]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Add))
        settings_bar.addAction(self.add_act)
        self.move_act = QtWidgets.QAction('Move', mouse_group, shortcut='Ctrl+E',
                icon=qt_icon('move_point'), toolTip='Dragging mouse moves a marker [Ctrl+E]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Move))
        settings_bar.addAction(self.move_act)
        self.erase_multi_act = QtWidgets.QAction('Erase M', mouse_group, shortcut='Ctrl+D',
                icon=qt_icon('erase'), toolTip='Draw a contour to erase all markers inside [Ctrl+D]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseMulti))
        settings_bar.addAction(self.erase_multi_act)
        self.erase_single_act = QtWidgets.QAction('Erase S', mouse_group, shortcut='Ctrl+W',
                icon=qt_icon('erase_point'), toolTip='Mouse click erases a marker [Ctrl+W]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Remove))
        settings_bar.addAction(self.erase_single_act)
        settings_bar.addSeparator()

        self.undo_act = QtWidgets.QAction('Undo', self, shortcut='Ctrl+Z',
                icon=qt_icon('undo'),
                toolTip='Undo last Add, Move or Erase operation [Ctrl+Z]',
                triggered=self._undo)
        settings_bar.addAction(self.undo_act)
        settings_bar.addSeparator()
        #
        settings_bar.addAction(self.toggle_visibility)
        self.disp_act = QtWidgets.QAction('Settings', shortcut='F5',
                icon=qt_icon('settings'), toolTip='Change Display Settings [F5]',
                triggered=self._show_display_settings)
        settings_bar.addAction(self.disp_act)
        settings_bar.addAction(self.snap_annotated_act)
        settings_bar.addSeparator()
        #
        self.detect_act = QtWidgets.QAction('Detect', self, shortcut='Ctrl+G',
                icon=qt_icon('fovea'),
                toolTip='Detect RPE cells [Ctrl+G]',
                triggered=self._detect_RPE_cells)
        settings_bar.addAction(self.detect_act)
    #
    def _on_hotkey_act(self):
        dlg = ao_hotkey_dialog(self, self._action_map, self._default_key_map)
        dlg.update_key_map(self.hotkeys)
        if dlg.exec_():
            self.hotkeys = dlg.key_map
            self.saveShortcuts()
    #
    def _display_about(self):
        dlg = AboutDialog(self)
        dlg.exec()
    #
    def _display_help(self):
        self.helpWindow = helpWindow = QtWidgets.QWidget()
        helpWindow.setWindowTitle(cfg.APP_NAME)
        helpWindow.setWindowIcon(qt_icon('help'))

        layout = Qt.QVBoxLayout()
        helpWindow.setLayout(layout)

        helpBrowser = QtWidgets.QTextBrowser()
        helpBrowser.setOpenExternalLinks(True)
        layout.addWidget(helpBrowser)

        helpFile = os.path.join(HELP_DIR, 'rpedetect.html')
        if os.path.isfile(helpFile):
            url = QtCore.QUrl.fromLocalFile(helpFile)
            helpBrowser.setSource(url)
        else:
            helpBrowser.setText("Sorry, no help available at this time.")

        geom = QtWidgets.QApplication.primaryScreen().geometry()
        helpWindow.setMinimumSize(geom.width() * 60 // 100, geom.height() * 56 // 100)
        helpWindow.move(geom.width() * 20 // 100, geom.height() * 14 // 100)

        helpWindow.showNormal()
    #
    def _open_image_list(self, img_filenames, save_state=False):
        img_dir = None
        if len(img_filenames) == 0:
            return
        self._initialize_input_data()
        self._image_view.reset_color()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Open Images')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)

        for idx, img_name in enumerate(img_filenames):
            try:
                itk_img = self._file_io.read_image(img_name)
                assert len(itk_img.GetSize()) in (2, 3)
            except Exception as ex:
                print(f'Failed to open {img_name}, possibly wrong format: {ex}')
                continue
            imdat = InputImageData(img_name, itk_img)
            imdat.hist_apath = self.hist.get_history_file(img_name)
            imdat.local_apath = self.hist.get_local_file(img_name)
            self._input_data.append(imdat)

            if img_dir is None:
                img_dir = os.path.abspath(os.path.dirname(img_name))

            aa = {}
            save_hist = False
            if os.path.isfile(imdat.hist_apath):
                aa = self._file_io.read_annotations(imdat.hist_apath)
            elif os.path.isfile(imdat.local_apath):
                aa = self._file_io.read_annotations(imdat.local_apath)
                save_hist = True

            imdat.importAnnotations(aa)
            if save_hist:
                self._file_io.write_points(imdat.hist_apath, imdat.exportAnnotations(),
                        imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())

            self._progress_dlg.set_progress((idx+1)/float(len(img_filenames))* 100)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        self._update_listwidget()
        self._image_view.image_visibility = True
        self._display_image(0)
        self._cur_img_id = 0
        self._file_list.setCurrentRow(self._cur_img_id)

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
        #
        if img_dir is None:
            img_dir = ''
        elif save_state:
            self.saveDir = self.loadDir = QtCore.QDir(img_dir)
            self.saveState()

        self._status_bar.showMessage(img_dir)
    #
    def selected_imdat(self):
        if len(self._input_data) == 0 or self._cur_img_id == -1:
            return None
        return self._input_data[self._cur_img_id]
    def _snap_annotated(self):
        imdat = self.selected_imdat()
        if imdat is None: return
        dlg = ao_snap_dialog(parent=self, glyph_scale=0.5)
        dlg.setWindowTitle(imdat.listname+' - Snapshot')
        dlg.setWindowIcon(qt_icon('ConeDetectionML.png'))
        dlg.setImageData(
            imdat.filepath,
            imdat.GetNdArray(),
            displaySettings=self._image_view.displaySettings,
            colorInfo=self._image_view.color_info,
        )
        dlg.setPoints(imdat.annotations)
        dlg.exec_()
    #
    def _open_images(self):
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["RPE Images (*.tif)", "Annotation files (*.csv)"])
        file_dialog.setNameFilter("RPE Images (*.tif)")
        file_dialog.setWindowTitle('Open RPE images')
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        file_dialog.setWindowFilePath(QtCore.QDir.homePath())
        file_dialog.setDirectory(self.loadDir)
        file_dialog.exec()

        img_filenames = file_dialog.selectedFiles()
        if len(img_filenames) > 0:
            self.saveDir = self.loadDir = file_dialog.directory()
            self.saveState()
        filter = file_dialog.selectedNameFilter()

        self._open_image_list(img_filenames)
    #
    def _get_data_index(self, csv_file_path, strict=True):
        fn = os.path.basename(csv_file_path)
        bn, ext = os.path.splitext(fn)
        for id, imdat in enumerate(self._input_data):
            if strict:
                if bn == imdat.name:
                    return id
        else:
            if bn.startswith(imdat.name):
                return id
        return -1

    def _open_annotations(self):
        if len(self._input_data) == 0 or self._cur_img_id == -1:
            display_error('No AO images', 'Please load AO images first!')
            return

        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilter("Annotation files (*.csv)")
        file_dialog.setWindowTitle('Open RPE annotations')
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        file_dialog.setWindowFilePath(QtCore.QDir.homePath())
        file_dialog.setDirectory(self.saveDir)
        file_dialog.exec()

        csv_filenames = file_dialog.selectedFiles()
        if len(csv_filenames) is not 0:
            self.saveDir = file_dialog.directory()
            self.saveState()
            if display_warning("Replace annotations", "Do you want to load annotations to replace current ones?")\
                     == QtWidgets.QMessageBox.Ok:
                self._open_annotation_list(csv_filenames)
    #
    def _open_annotation_list(self, csv_filenames, strict=True):
        err_files = []
        for csv_file in csv_filenames:
            id = self._get_data_index(csv_file, strict)
            if id != -1:
                imdat = self._input_data[id]
                try:
                    aa = self._file_io.read_annotations(csv_file, False)
                except Exception:
                    err_files.append(os.path.basename(csv_file))
                    continue

                imdat.aclear()
                imdat.importAnnotations(aa)
                self._file_io.write_points(imdat.hist_apath, imdat.exportAnnotations(),
                        imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())

        if self._cur_img_id >= 0:
            self._display_image(self._cur_img_id)
        if len(err_files) > 0:
            if len(err_files) > 5:
                err_files = err_files[:4] + ['... +%d more.' % (len(err_files)-4,)]
            display_error('Failed to read the following file(s):', '\n'.join(err_files) + \
                '\n(do you attempt to open spreadsheet(s) generated by other applications?)')
    #
    def _show_data_locations(self):
        if self._cur_img_id < 0 or self._cur_img_id >= len(self._input_data):
            return
        imdat = self._input_data[self._cur_img_id]
        #
        img_path = os.path.abspath(imdat.filepath)
        self._data_loc_dlg.setPaths(imdat.itk_img, img_path, imdat.local_apath, imdat.hist_apath)
        self._data_loc_dlg.exec()
    #
    def next_image(self):
        if self._file_list.currentRow() < self._file_list.count() - 1:
            self._file_list.setCurrentRow(self._file_list.currentRow() + 1)
    def previous_image(self):
        if self._file_list.currentRow() > 0:
            self._file_list.setCurrentRow(self._file_list.currentRow() - 1)
    def _file_list_row_changed(self, newrow):
        if self._cur_3d:
            imdat = self._cur_3d
            imdat.color = self._image_view.color_info
            if newrow > 0 and newrow <= imdat.nframes:
                imdat.cframe = newrow - 1
                self._display_image(self._cur_img_id)
            return
        if self._cur_img_id >= 0:
            imdat = self._input_data[self._cur_img_id]
            imdat.color = self._image_view.color_info
        self._cur_img_id = newrow
        self._display_image(self._cur_img_id)
    def _file_list_item_doublecklicked(self, item):
        row = self._file_list.row(item)
        if self._cur_3d:
            if row == 0:
                self._cur_3d = None
                row = self._cur_img_id
            else:
                row = -1
        else:
            imdat = self._input_data[row]
            if imdat.nframes > 1:
                self._cur_img_id = row
                self._cur_3d = imdat
                row = imdat.cframe + 1
            else:
                row = -1
        if row >= 0:
            self._update_listwidget(newlist=True)
            self._file_list.setCurrentRow(row)
    #
    def _file_list_item_changed(self, item):
        if self._mute or self._cur_3d is None: return
        self._mute = True
        row = self._file_list.row(item)
        checked = item.checkState() == QtCore.Qt.Checked
        imdat = self._cur_3d
        if row == 0:
            check = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
            for i in range(1, self._file_list.count()):
                self._file_list.item(i).setCheckState(check)
                imdat.setChecked(i-1, checked)
        else:
            imdat.setChecked(row-1, checked)
        self._mute = False
        if row != self._file_list.currentRow():
            self._file_list.setCurrentRow(row)
    #
    # def __check_z(self, idx):
    #     markers = self._input_data['RPE annotations'][idx]
    #     zmap = defaultdict(int)
    #     for pt in markers:
    #         zmap[pt[2]] += 1
    #     print(self._input_data['RPE image names'][idx], zmap)
    #
    def _set_annotations(self, idx=None):
        if idx is None:
            idx = self._cur_img_id
        if idx < 0 or idx >= len(self._input_data):
            return
        imdat = self._input_data[idx]
        self._image_view.set_annotations(imdat.annotations)
    #
    def _display_image(self, idx):
        self._image_view.initialization()
        if idx < 0 or idx >= len(self._input_data):
            return
        imdat = self._input_data[idx]
        self._image_view.set_image(imdat.itk_img, n_array=imdat.GetNdArray())
        self._image_view.set_annotations(imdat.annotations)
        self._image_view.set_image_name(imdat.hist_apath)
        self._image_view.reset_view(True)
        self._image_view.color_info = imdat.color
        self._image_view.visibility = True
        self._sync_display_controls()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
        if hasattr(self, 'srcwin'):
            self.srcwin.hide()
        self._status_bar.showMessage(f'{imdat.statusname}')
    #
    def write_history(self, pts=None):
        if self._cur_img_id < 0 or self._cur_img_id >= len(self._input_data):
            return
        imdat = self._input_data[self._cur_img_id]
        if pts:
            imdat.annotations = pts
        self._file_io.write_points(imdat.hist_apath, imdat.exportAnnotations(), imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())
    #
    def _detect_RPE_cells(self):
        #res = AOSettingsDialog.display_warning('Detecting RPE cells', 'Do you really want to detect cells?')
        self._detection_para_dlg.SetImageList([imdat.name for imdat in self._input_data])
        c_rows = [row for row, imdat in enumerate(self._input_data) if imdat.acount() == 0]
        self._detection_para_dlg.SetCheckedRows(c_rows)
        self._detection_para_dlg.SetHighlightedRow(self._cur_img_id)
        self._detection_para_dlg.update_builtin_weights()
        res = self._detection_para_dlg.exec_()
        if res == QtWidgets.QDialog.Rejected:
            return

        c_rows = [row for row in self._detection_para_dlg.checkedRows() if self._input_data[row].countChecked() > 0]
        self.saveState()

        progr_total = sum([self._input_data[row].countChecked() for row in c_rows])
        if progr_total == 0:
            display_error('Input error', 'Nothing was checked.')
            return

        mw = self._detection_para_dlg.model_weights
        if mw is None:
            display_error('Input errors', 'Missing Detection Model Weights!')
            return
        method, weights = mw
        self._status_bar.showMessage('Using Detection Model Weights from: '+weights)

        window_title = cfg.APP_NAME + ': ' + weights
        self.setWindowTitle(window_title)

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Detecting RPEs ...')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)
        progr_cur = 0

        self._detection.create_detection_model(method, weights)

        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        for i, row in enumerate(c_rows):
            imdat = self._input_data[row]

            kwarg = {
                'user': '=auto=',
                'method': method,
                'FOV': self._detection_para_dlg.image_fov,
                'probablity_threshold': self._detection_para_dlg.probablity_threshold,
                'clustering_radius': self._detection_para_dlg.clustering_radius,
            }

            o = imdat.itk_img.GetOrigin()
            s = imdat.itk_img.GetSpacing()
            aa_src = {}
            if imdat.nframes > 1:
                n_array = sitk.GetArrayFromImage(imdat.itk_img)
                for fr in range(imdat.nframes):
                    if not imdat.isChecked(fr): continue
                    itk_img = sitk.GetImageFromArray(n_array[fr])
                    detection_pts = self._detection.detect_RPEs(itk_img, self._detection_para_dlg.image_fov,
                            self._detection_para_dlg.probablity_threshold, self._detection_para_dlg.clustering_radius)
                    aa_src[fr] = [[o[0] + pt[0]*s[0], o[1] + pt[1]*s[1], -0.001] for pt in detection_pts]
                    progr_cur += 1
                    self._progress_dlg.set_progress(float(progr_cur)/float(progr_total) * 100.)
                    QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            else:
                detection_pts = self._detection.detect_RPEs(imdat.itk_img, self._detection_para_dlg.image_fov,
                            self._detection_para_dlg.probablity_threshold, self._detection_para_dlg.clustering_radius)
                aa_src[0] = [[o[0] + pt[0]*s[0], o[1] + pt[1]*s[1], -0.001] for pt in detection_pts]
                progr_cur += 1
                self._progress_dlg.set_progress(float(progr_cur)/float(progr_total) * 100.)
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

            aa = {}
            for fr, src_pts in aa_src.items():
                mc = MetaList(src_pts, meta=MetaMap(MetaRecord(**kwarg)))
                #mc.meta.addmeta(MetaRecord(), setdefault=True)
                aa[fr] = mc
            imdat.aclear()
            imdat.importAnnotations(aa)

            self._file_io.write_points(imdat.hist_apath, imdat.exportAnnotations(), imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())

        if not self._cur_img_id in c_rows:
            self._file_list.setCurrentRow(c_rows[0])
        else:
            self._image_view.set_annotations(self._input_data[self._cur_img_id].annotations)
            self._image_view.reset_view()

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
        self._image_view.visibility = True
        self._sync_display_controls()

    def _save_data(self):
        if len(self._input_data) == 0: return
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
            dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                    'Select saving directory', sdir)
            if dir_name:
                for imdat in self._input_data:
                    fn = os.path.basename(imdat.local_apath)
                    apath = os.path.abspath(os.path.join(dir_name, fn))
                    self._file_io.write_points(apath, imdat.exportAnnotations(), imdat.GetOrigin(), imdat.GetSpacing())
                #self._file_io.write_annotations(dir_name, self._input_data)
                self._update_listwidget(newlist=False)
                self.saveDir = QtCore.QDir(dir_name)
                self.saveState()
        except Exception as ex:
            display_error('Error saving data', str(ex))

    def _delete_all(self, event):
        if self._cur_img_id < 0: return
        imdat = self._input_data[self._cur_img_id]
        if imdat.acount() == 0: return
        if not askYesNo('Confirm',
                'You are about to delete all annotations \non the current image.',
                detail='This operation can not be undone. \nContinue?'):
            return
        self._image_view.visibility = True
        self._sync_display_controls()
        imdat.aclear()
        self.write_history(pts=None)
        self._image_view.set_annotations(imdat.annotations)
        self._image_view.reset_view(False)

    def _quit(self, event):
        self.close()

    def _set_mouse_mode(self, m=MouseOp.Normal):
        self._mouse_status = m
        self._image_view.set_mouse_mode(self._mouse_status)
        if m != MouseOp.Normal:
            if hasattr(self, 'bcwin') and not self.bcwin.manual:
                self.bcwin.close()
                del self.bcwin
                self._mute = True
                self.bc_act.setChecked(False)
                self._mute = False

    def _sync_display_controls(self):
        self._mute = True
        self.toggle_interpolation.setChecked(self._image_view.interpolation)
        self.voronoi_act.setChecked(self._image_view.voronoi)
        self.toggle_visibility.setChecked(self._image_view.visibility)
        self._mute = False
    def _on_display_settings(self, param):
        self._image_view.displaySettings = param
        self._sync_display_controls()
        self._image_view.reset_view(False)
        self.saveState()
    #
    def _undo(self):
        self._image_view.visibility = True
        self._sync_display_controls()
        self._image_view.undo()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
    #
    def _toggle_visibility(self):
        if not self._mute:
            self._image_view.visibility = self.toggle_visibility.isChecked()
    #
    def _toggle_interpolation(self):
        if not self._mute:
            self._image_view.interpolation = self.toggle_interpolation.isChecked()
            self._image_view.reset_view()
            self.saveState()
    #
    def _toggle_voronoi(self):
        if not self._mute:
            self._image_view.voronoi = self.voronoi_act.isChecked()
            self.saveState()
    #
    def _reset_brightness_contrast(self):
        self._image_view.reset_color()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
        if self._cur_img_id >= 0:
            self._input_data[self._cur_img_id].color = self._image_view.color_info
        self._image_view.reset_view(True)
        self._image_view.image_visibility = True
    #
    def _findpoint(self, x, y, pts, delta=5.):
        if not pts:
            return -1
        dsq = delta*delta
        for i, pt in enumerate(pts):
            dist = (pt[0]-x)**2 + (pt[1]-y)**2
            if dist < dsq:
                return i
        return -1
    def trackMousePos(self, x, y):
        msg = ''
        ptidx = self._findpoint(x, y, None if self._cur_img_id < 0 else self._input_data[self._cur_img_id].annotations)
        if ptidx >= 0:
            pts = self._input_data[self._cur_img_id].annotations
            if hasattr(pts, 'objmeta'):
                pt = pts[ptidx]
                meta = pts.objmeta(pt)
                msg = f'({pt[0]:.0f},{pt[1]:.0f}): {meta}'
        if ptidx != self._status_id:
            self._status_id = ptidx
            self.status(msg, temp=True)
    #
    def _update_sources(self):
        self._mute = True
        self._set_annotations(self._cur_img_id)
        self._image_view.reset_view()
        self._mute = False
    #
    def resetSources(self, update=False):
        id = self._cur_img_id
        if id < 0: return
        annotations = self._input_data[id].annotations
        if hasattr(annotations, 'setGrayMeta'):
            annotations.setGrayMeta([])
        self._set_annotations(self._cur_img_id)
        if update:
            self._image_view.reset_view()
    #
    def _select_annotation_sources(self, e):
        id = self._cur_img_id
        if id < 0: return
        annotations = self._input_data[id].annotations

        self._image_view.visibility = True
        self._sync_display_controls()
        self._image_view.reset_view()

        if not hasattr(self, 'srcwin'):
            self.srcwin = ao_source_window(self)
        self.srcwin.setMetaList(annotations)
        self.srcwin.show()
        self.srcwin.activateWindow()
    #

    @property
    def mouse_status(self):
        return self._mouse_status

    def _show_display_settings(self, e):
        self._display_settings_dlg.displaySettings = self._image_view.displaySettings
        self._display_settings_dlg.showNormal()
    #
    def onBCci(self, ci):
        #self.push_color_undo(self._image_view.color_info)
        self._image_view.color_info = ci
    def onIWci(self, ci):
        if not hasattr(self, 'bcwin'):
            self.bcwin = ao_brightness_contrast(self, parent=self.vtkFrame, callback=self.onBCci)
            self.bcwin.color_info = self._image_view.color_info
            self.bcwin.manual = False
            self._mute = True
            self.bc_act.setChecked(True)
            self._mute = False
        else:
            self.bcwin.color_info = ci
        self.bcwin.show()
    def _toggle_brightness_contrast(self):
        if self._mute: return
        if self.bc_act.isChecked():
            if not hasattr(self, 'bcwin'):
                self.bcwin = ao_brightness_contrast(self, parent=self.vtkFrame, callback=self.onBCci)
            self.bcwin.color_info = self._image_view.color_info
            self.bcwin.show()
            self.bcwin.activateWindow()
        else:
            if hasattr(self, 'bcwin'):
                self.bcwin.close()
                del self.bcwin
    #
    def _save_stats(self):
        if len(self._input_data) == 0: return
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
            dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                    'Select Export directory', sdir)
            if not dir_name:
                return

            cnt = self._file_io.write_annotation_stats(dir_name, self._input_data)
            self.status('%d Annotation Tracker Statistics file(s) exported to %s' % (cnt, dir_name))
            #self._update_listwidget(self._input_data['image file paths'], newlist=False)
            #self.saveDir = QtCore.QDir(dir_name)
            #self.saveState()
        except Exception as ex:
            display_error('Error annotation stats', ex)
    #
