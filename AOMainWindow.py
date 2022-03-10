from __future__ import division
import os, sys
import json
import vtk

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
# import matplotlib.pyplot as plt
import SimpleITK as sitk

import numpy as np
from keras.preprocessing.image import load_img
import AOImageView
from AOImageView import MouseOp
import AOFileIO
import AOMethod
import AOSettingsDialog
from AOSettingsDialog import ao_parameter_dialog
from AOSettingsDialog import ao_progress_dialog, ao_loc_dialog
from AOSettingsDialog import display_error, display_warning
import AOConfig as cfg

BASE_DIR = os.path.dirname(__file__)
ICONS_DIR = os.path.join(BASE_DIR, 'Icons')
HELP_DIR = os.path.join(BASE_DIR, 'Help')
def qt_icon(name):
    return QtGui.QIcon(os.path.join(ICONS_DIR, name))

_big_icon = QtCore.QUrl.fromLocalFile(os.path.join(ICONS_DIR, 'RPE_Detection256x256.png'))
about_html = '''
<table><tr>
<td><img src="%s">&nbsp;&nbsp;</td>
<td><b>%s %s</b><div>
Tam lab<br>
National Eye Institute<br>
National Institutes of Health</div><div><br>
RPE Cell Detection (Machine Learning edition)<br><br>
<i>Jianfei Liu (NEI/NIH), Andrei Volkov (NEI/NIH Contractor), and Johnny Tam (NEI/NIH),<br>
with research support from the Intramural Research Program<br>
of the National Institutes of Health.</i>
</td></tr></table>
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
        #
        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        #
        layout.addWidget(lbl)
        layout.addWidget(buttonbox)
        self.setLayout(layout)
#

def display_error(err, ex):
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    if isinstance(ex, Exception):
        msg.setText('Exception:')
    else:
        msg.setText('Error:')
    msg.setInformativeText(str(ex))
    msg.setWindowTitle(err)
    msg.exec_()
#
    
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

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.setWindowIcon(qt_icon('RPE_Detection.png'))

        cfg.main_wnd = self

        self._input_data = {
            'RPE image file paths': [],
            'RPE image names': [],
            'RPE images': [],
            'RPE annotations': [],
            'colors': [],
        }
        self._cur_img_id = -1
        self.loadDir = QtCore.QDir.home()
        self.saveDir = QtCore.QDir.home()

        # State dir/file
        self.state_dir = os.path.join(os.path.expanduser('~'), '.RPE_Detection')
        if not os.path.exists(self.state_dir):
            os.mkdir(self.state_dir)
        self.state_file = os.path.join(self.state_dir, 'state.json')

        #create backup directory
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

        self._detection_para_dlg = ao_parameter_dialog(self)
        self._detection_para_dlg.setMinimumSize(geom.width()/5, geom.height()/3)
        self._progress_dlg = ao_progress_dialog(self)
        self._progress_dlg.setMinimumWidth(geom.width()/5)
        self._file_io = AOFileIO.ao_fileIO()
        self._detection = AOMethod.ao_method()
        self._detection_model_names = self._detection.create_detection_models('model_weights')
        self._detection_para_dlg.set_detection_weights(self._detection_model_names)
        #self._detection.create_detection_model('RPE_detection_region_weights.h5')
        #self._detection.create_detection_model('model_weights/RPE_detection_region_centroid_weights.h5')
        #self._detection.create_detection_model('RPE_detection_weights.h5')
        self._data_loc_dlg = ao_loc_dialog(self)
        self._data_loc_dlg.setMinimumWidth(geom.width()/2)
        
        self.loadState()
        self.setAcceptDrops(True)
    #
    def loadState(self):
        try:
            with open(self.state_file, 'r') as fi:
                jobj = json.load(fi)
            if 'annotation_size' in jobj:
                self._annotation_size_input.setValue(int(jobj['annotation_size']))
            self._detection_para_dlg.set_state(jobj['detection_para'])
            if 'loadDir' in jobj:
                self.loadDir = QtCore.QDir(jobj['loadDir'])
            if 'saveDir' in jobj:
                self.saveDir = QtCore.QDir(jobj['saveDir'])
        except Exception:
            pass
    def saveState(self):
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
                'detection_para': self._detection_para_dlg.get_state(),
                'annotation_size': self._annotation_size_input.value(),
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

    def _initialize_input_data(self):
        self._input_data['RPE image file paths'].clear()
        self._input_data['RPE image names'].clear()
        self._input_data['RPE images'].clear()
        self._input_data['RPE annotations'].clear()
        self._input_data['colors'].clear()

    def _setup_layout(self):
        frame = Qt.QFrame()
        self._file_list = QtWidgets.QListWidget(self)
        self._file_list.currentRowChanged.connect(self._file_list_row_changed)

        vtkWidget = QVTKRenderWindowInteractor(frame)
        self._image_view = AOImageView.ao_visualization(vtkWidget, self._mouse_status)
        
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
        self.open_image_act = QtWidgets.QAction('Open Images...', self, shortcut=QtGui.QKeySequence.Open,
                                      icon=qt_icon('open'),
                                      statusTip='Open RPE images/annotations',
                                      triggered=self._open_images)

        self.open_annotation_act = QtWidgets.QAction('Open Annotations...', self,
                                       icon=qt_icon('open_document1'),
                                       statusTip='Open RPE annotations', triggered=self._open_annotations)

        self.save_data_act = QtWidgets.QAction('Save Annotations...', self, shortcut=QtGui.QKeySequence.Save,
                                      icon=qt_icon('save'),
                                      statusTip='Save RPE annotations', triggered=self._save_data)

        self.delete_all_act = QtWidgets.QAction('Delete Annotations', self,
                                      statusTip='Delete all RPE annotations on current image', triggered=self._delete_all)

        quit = QtWidgets.QAction('Exit', self, shortcut=QtGui.QKeySequence.Quit,
                                 statusTip="Quit the application",
                                 triggered=self._quit)
        
        self.toggle_visibility = QtWidgets.QAction('Annotation Visibility', self, shortcut='F2',
                    checkable=True, checked=True,
                    statusTip='Toggle Annotation Visibility (F2)',
                    triggered=self._toggle_visibility)

        self.reset_brightness_contrast = QtWidgets.QAction('Reset Image View', self, shortcut='F10',
                    statusTip='Reset Image View to the original size, position, brightness/contrast, etc.',
                    triggered=self._reset_brightness_contrast)

        self.data_loc_act = QtWidgets.QAction('Show data file locations', self, shortcut='Ctrl+L',
                    statusTip='Show data locations of the current image file',
                    triggered=self._show_data_locations)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_image_act)
        file_menu.addAction(self.open_annotation_act)
        file_menu.addAction(self.save_data_act)
        file_menu.addSeparator()
        file_menu.addAction(self.delete_all_act)
        file_menu.addSeparator()
        file_menu.addAction(quit)
        
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.toggle_visibility)
        view_menu.addAction(self.reset_brightness_contrast)
        view_menu.addSeparator()
        view_menu.addAction(self.data_loc_act)

        self.about_act = QtWidgets.QAction('About', self,
                    icon=qt_icon('about'),
                    triggered=self._display_about)
        self.help_act = QtWidgets.QAction('Keyboard Shortcuts...', self, shortcut='F1',
                    icon=qt_icon('help'),
                    toolTip='Display list of keyboard shortcuts',
                    statusTip='Display list of keyboard shortcuts',
                    triggered=self._display_help)
        
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_act)
        help_menu.addAction(self.help_act)

        self._next_image_act = QtWidgets.QAction('NextImage', self,
                    shortcut='Down', triggered=self.next_image)
        self._prev_image_act = QtWidgets.QAction('PreviousImage', self,
                    shortcut='Up', triggered=self.previous_image)
    #
    def _update_listwidget(self, image_paths, newlist=True):
        if len(image_paths) != self._file_list.count():
            newlist = True
        if newlist:
            self._file_list.clear()
            for img_path in image_paths:
                bn, _ = os.path.splitext(os.path.basename(img_path))
                self._file_list.addItem(self.hist.get_list_name(img_path))
        else:
            for row, img_path in enumerate(image_paths):
                self._file_list.item(row).setText(self.hist.get_list_name(img_path))

    def _setup_toolbar(self):
        settings_bar = self.addToolBar("Settings")
        settings_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        
        open_image_button = QtWidgets.QToolButton()
        open_image_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        open_image_button.setDefaultAction(self.open_image_act)
        open_image_button.setText("Images")
        open_image_button.setToolTip("Open RPE Images/Annotations (Ctrl+O)")

        open_annotation_button = QtWidgets.QToolButton()
        open_annotation_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        open_annotation_button.setDefaultAction(self.open_annotation_act)
        open_annotation_button.setText("Points")
        open_annotation_button.setToolTip("Open RPE Annotations")

        save_data_button = QtWidgets.QToolButton()
        save_data_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        save_data_button.setDefaultAction(self.save_data_act)
        save_data_button.setText("Save")
        save_data_button.setToolTip("Save RPE Annotations (Ctrl+S)")

        settings_bar.addWidget(open_image_button)
        settings_bar.addWidget(open_annotation_button)
        settings_bar.addWidget(save_data_button)
        settings_bar.addSeparator()

        # Mouse Op button group
        mouse_group = QtWidgets.QActionGroup(self)
        default_act = QtWidgets.QAction('Default', mouse_group, shortcut='Ctrl+M',
                icon=qt_icon('mouse'), toolTip='Default Mouse Mode (Ctrl+M)',
                checkable=True, checked=True,
                triggered=lambda: self._set_mouse_mode(MouseOp.Normal))
        settings_bar.addAction(default_act)
        add_act = QtWidgets.QAction('Add', mouse_group, shortcut='Ctrl+C',
                icon=qt_icon('draw_point'), toolTip='Mouse click adds a marker (Ctrl+C)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Add))
        settings_bar.addAction(add_act)
        move_act = QtWidgets.QAction('Move', mouse_group, shortcut='Ctrl+E',
                icon=qt_icon('move_point'), toolTip='Dragging mouse moves a marker (Ctrl+E)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Move))
        settings_bar.addAction(move_act)
        erase_multi_act = QtWidgets.QAction('Erase M', mouse_group, shortcut='Ctrl+D',
                icon=qt_icon('erase'), toolTip='Draw a contour to erase all markers inside (Ctrl+D)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseMulti))
        settings_bar.addAction(erase_multi_act)
        erase_single_act = QtWidgets.QAction('Erase S', mouse_group, shortcut='Ctrl+W',
                icon=qt_icon('erase_point'), toolTip='Mouse click erases a marker (Ctrl+W)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Remove))
        settings_bar.addAction(erase_single_act)
        
        voronoi_act = QtWidgets.QAction('Voronoi', mouse_group, shortcut='Ctrl+V',
                icon=qt_icon('Voronoi'), toolTip='Show Voronoi diagram',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.Voronoi))
        settings_bar.addAction(voronoi_act)
        
        settings_bar.addSeparator()

        self.undo_act = QtWidgets.QAction('Undo', self, shortcut='Ctrl+Z',
                icon=qt_icon('undo'),
                toolTip='Undo last Add, Move or Erase operation (Ctrl+Z)', 
                triggered=self._undo)
        settings_bar.addAction(self.undo_act)

        detection_setup_group = QtWidgets.QGroupBox()
        detection_setup_layout = QtWidgets.QGridLayout()
        self.annotation_pts_checkbox = \
            annotation_pts_checkbox = QtWidgets.QCheckBox('Annotation visibility')
        annotation_pts_checkbox.setChecked(True)
        annotation_pts_checkbox.stateChanged.connect(self._set_annotation_points_visibility)

        annotation_size_label = QtWidgets.QLabel('Annotation Size: ')
        self._annotation_size_input = QtWidgets.QSpinBox()
        self._annotation_size_input.setMinimum(1)
        self._annotation_size_input.setMaximum(100)
        self._annotation_size_input.setValue(12)
        self._annotation_size_input.valueChanged.connect(self._set_annotation_points_size)
        detection_setup_layout.addWidget(annotation_pts_checkbox, 0, 0, 1, 2)
        detection_setup_layout.addWidget(annotation_size_label, 1, 0)
        detection_setup_layout.addWidget(self._annotation_size_input, 1, 1)
        detection_setup_group.setLayout(detection_setup_layout)

        settings_bar.addWidget(detection_setup_group)
        settings_bar.addSeparator()

        self.detect_act = QtWidgets.QAction('Detect', self, shortcut='Ctrl+G',
                icon=qt_icon('fovea'),
                toolTip='Detect RPE cells (Ctrl+G)', 
                triggered=self._detect_RPE_cells)
        settings_bar.addAction(self.detect_act)
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
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Open Images')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)

        for idx, img_name in enumerate(img_filenames):
            itk_img = self._file_io.read_image(img_name)
            self._input_data['RPE images'].append(itk_img)
            self._input_data['RPE image file paths'].append(img_name)
            self._input_data['RPE image names'].append(os.path.splitext(os.path.basename(img_name))[0])
            self._input_data['colors'].append((127.5, 255.))

            if img_dir is None:
                img_dir = os.path.abspath(os.path.dirname(img_name))

            annotated_pts = []
            #extract annotation file
            history_file_name = self.hist.get_history_file(img_name)
            local_file_name = self.hist.get_local_file(img_name)
            
            # Read history first as it may contain more up to date info
            if os.path.isfile(history_file_name):
                annotated_pts = self._file_io.read_annotations(history_file_name)
            elif os.path.isfile(local_file_name):
                annotated_pts = self._file_io.read_annotations(local_file_name)
            
            if len(annotated_pts)>0 and self._file_io.is_annotation_spaced(annotated_pts, itk_img):
                annotated_pts = self._file_io.scale_annotations(annotated_pts, itk_img)
            self._input_data['RPE annotations'].append(annotated_pts)
            self._file_io.write_points(history_file_name, self._input_data['RPE annotations'][idx],
                                       itk_img.GetOrigin(), itk_img.GetSpacing())

            self._progress_dlg.set_progress((idx+1)/float(len(img_filenames))* 100)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        self._update_listwidget(self._input_data['RPE image file paths'])
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
        for id, img_name in enumerate(self._input_data['RPE image names']):
            if strict:
                if bn == img_name: return id
            else:
                if bn.startswith(img_name): return id
        return -1

    def _open_annotations(self):
        if len(self._input_data['RPE images']) == 0 or self._cur_img_id == -1:
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
                self._open_annotation_list(csv_filenames, strict=False)
    #        
    def _open_annotation_list(self, csv_filenames, strict=True):
        err_files = []
        for csv_file in csv_filenames:
            id = self._get_data_index(csv_file, strict)
            if id != -1:
                try:
                    annotated_pts = self._file_io.read_annotations(csv_file, False)
                except Exception:
                    err_files.append(os.path.basename(csv_file))
                    continue
                if self._file_io.is_annotation_spaced(annotated_pts, self._input_data['RPE images'][id]):
                    annotated_pts = self._file_io.scale_annotations(annotated_pts,
                                                                    self._input_data['RPE images'][id])
                self._input_data['RPE annotations'][id] = annotated_pts

                history_file_name = self.hist.get_history_file(self._input_data['RPE image file paths'][id])
                self._file_io.write_points(history_file_name, self._input_data['RPE annotations'][id],
                                           self._input_data['RPE images'][id].GetOrigin(),
                                           self._input_data['RPE images'][id].GetSpacing())
        if self._cur_img_id >= 0:
            self._display_image(self._cur_img_id)
        if len(err_files) > 0:
            if len(err_files) > 5:
                err_files = err_files[:4] + ['... +%d more.' % (len(err_files)-4,)]
            display_error('Failed to read the following file(s):', '\n'.join(err_files) + \
                '\n(do you attempt to open spreadsheet(s) generated by other applications?)')
    #
    def _show_data_locations(self):
        if self._cur_img_id < 0 or self._cur_img_id >= len(self._input_data['RPE image file paths']):
            return
        img = self._input_data['RPE images'][self._cur_img_id]
        img_path = os.path.abspath(self._input_data['RPE image file paths'][self._cur_img_id])
        loc_path = self.hist.get_local_file(img_path)
        hist_path = self.hist.get_history_file(img_path, False)
        self._data_loc_dlg.setPaths(img, img_path, loc_path, hist_path)
        self._data_loc_dlg.exec()
    #
    def next_image(self):
        if self._file_list.currentRow() < self._file_list.count() - 1:
            self._file_list.setCurrentRow(self._file_list.currentRow() + 1)
    def previous_image(self):
        if self._file_list.currentRow() > 0:
            self._file_list.setCurrentRow(self._file_list.currentRow() - 1)
    def _file_list_row_changed(self, newrow):
        if self._cur_img_id >= 0:
            self._input_data['colors'][self._cur_img_id] = self._image_view.color_info
        self._cur_img_id = newrow
        self._display_image(self._cur_img_id)
    #
    def _display_image(self, idx):
        self._image_view.initialization()
        self._image_view.set_image(self._input_data['RPE images'][idx])
        self._image_view.set_annotations(self._input_data['RPE annotations'][idx])

        history_file_name = self.hist.get_history_file(self._input_data['RPE image file paths'][idx])
        self._image_view.set_image_name(history_file_name)
        self._image_view.reset_view(True)
        self._image_view.color_info = self._input_data['colors'][idx]
        self.annotation_pts_checkbox.setChecked(True)
    #
    def _detect_RPE_cells(self):
        #res = AOSettingsDialog.display_warning('Detecting RPE cells', 'Do you really want to detect cells?')
        self._detection_para_dlg.SetImageList(self._input_data['RPE image names'])
        c_rows = [row for row, ann in enumerate(self._input_data['RPE annotations']) if len(ann) == 0]
        self._detection_para_dlg.SetCheckedRows(c_rows)
        self._detection_para_dlg.SetHighlightedRow(self._cur_img_id)
        res = self._detection_para_dlg.exec()
        if res == QtWidgets.QDialog.Rejected:
            return
        
        c_rows = self._detection_para_dlg.checkedRows()
        self.saveState()
        if len(c_rows) == 0:
            display_error('Input error', 'Nothing was checked.')
            return

        if self._detection_model_names.get(self._detection_para_dlg.get_current_detection_method()) == None \
            or len(self._input_data['RPE images']) == 0:
            display_error('Input errors', 'There are either no detection models or input data!')
            return

        window_title = cfg.APP_NAME + ': ' + self._detection_para_dlg.get_current_detection_method()
        self.setWindowTitle(window_title)

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Detecting RPEs ...')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)

        self._detection.create_detection_model(self._detection_para_dlg.get_current_detection_method(),
                                               self._detection_model_names[self._detection_para_dlg.get_current_detection_method()])

        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        for i, row in enumerate(c_rows):
            annotations = self._input_data['RPE annotations'][row]
            img = self._input_data['RPE images'][row]
            img_name = self._input_data['RPE image file paths'][row]
            # res_img = self._detection.detect_RPEs(img)
            # plt.imshow(res_img, cmap='gray')
            # plt.show()
            detection_pts = self._detection.detect_RPEs(img, self._detection_para_dlg.get_image_fov(),
                                                        self._detection_para_dlg.get_probablity_threshold(),
                                                        self._detection_para_dlg.get_clustering_radius())

            annotations.clear()
            for pt in detection_pts:
                tmp_pt = []
                tmp_pt.append(img.GetOrigin()[0] + img.GetSpacing()[0] * pt[0])
                tmp_pt.append(img.GetOrigin()[1] + img.GetSpacing()[1] * pt[1])
                # Add small negative value (-0.001) to Z-coordinate to make annotation
                # closer to the camera
                tmp_pt.append(-0.001)
                annotations.append(tmp_pt)

            history_file_name = self.hist.get_history_file(img_name)
            self._file_io.write_points(history_file_name, annotations, img.GetOrigin(), img.GetSpacing())

            self._progress_dlg.set_progress((i+1) / float(len(c_rows))* 100)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        if not self._cur_img_id in c_rows:
            self._file_list.setCurrentRow(c_rows[0])
        else:
            self._image_view.set_annotations(self._input_data['RPE annotations'][self._cur_img_id])
            self._image_view.reset_view()

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
        self.annotation_pts_checkbox.setChecked(True)

    def _save_data(self):
        if len(self._input_data['RPE images']) == 0:
            return
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
            dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                    'Select saving directory', sdir)
            if dir_name:
                self._file_io.write_annotations(dir_name, self._input_data)
                self._update_listwidget(self._input_data['RPE image file paths'], newlist=False)
                self.saveDir = QtCore.QDir(dir_name)
                self.saveState()
        except Exception as ex:
            display_error('Error saving data', ex)
            
    def _delete_all(self, event):
        id = self._cur_img_id
        if id < 0: return
        if len(self._input_data['RPE annotations'][id]) == 0: return
        if not askYesNo('Confirm',
                'You are about to delete all annotations \non the current image.',
                detail='This operation can not be undone. \nContinue?'):
            return
        self.annotation_pts_checkbox.setChecked(True)
        self._input_data['RPE annotations'][id] = []
        history_file_name = self.hist.get_history_file(self._input_data['RPE image file paths'][id])
        self._file_io.write_points(history_file_name, self._input_data['RPE annotations'][id],
                                   self._input_data['RPE images'][id].GetOrigin(),
                                   self._input_data['RPE images'][id].GetSpacing())
        self._image_view.set_annotations(self._input_data['RPE annotations'][id])
        self._image_view.reset_view(False)


    def _quit(self, event):
        self.close()

    def _set_mouse_mode(self, m=MouseOp.Normal):
        self._mouse_status = m
        self._image_view.set_mouse_mode(self._mouse_status)

    def _undo(self):
        self._image_view.undo()

    def _set_annotation_points_visibility(self, state):
        self._image_view.annotation_pts_visibility = state
        self._image_view.reset_view()
        self.toggle_visibility.setChecked(state)

    def _set_annotation_points_size(self):
        self._image_view.set_annotation_pts_size(self._annotation_size_input.value())
        self._image_view.reset_view()
        self.saveState()
        
    def _toggle_visibility(self):
        state = 0 if self._image_view.annotation_pts_visibility else 1
        self.annotation_pts_checkbox.setChecked(state)
    
    def _reset_brightness_contrast(self):
        self._image_view.reset_color()
        if self._cur_img_id >= 0:
            self._input_data['colors'][self._cur_img_id] = self._image_view.color_info
        self._image_view.reset_view(True)

    @property
    def mouse_status(self):
        return self._mouse_status

    def _show_settigns_dialog(self):
        self._settings.show()