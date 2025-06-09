import os
import sys
import time
import math

import numpy as np
from skimage.io import imread
from scipy.spatial import Voronoi
import SimpleITK as sitk
from PyQt5 import QtCore, QtWidgets, QtGui

from AODisplay import AoColorButton, ao_display_settings_dlg

# Clip a segment into a rectangular area
class SegmentClipper(object):
    Inside = 0
    Left = 1
    Right = 2
    Bottom = 4
    Top = 8
    def __init__(self, rect_dim):
        self.w = rect_dim[0]
        self.h = rect_dim[1]
        self.x0 = 0.001
        self.y0 = 0.001
        self.x1 = self.w - 0.001
        self.y1 = self.h - 0.001
    #
    def bnd_points(self):
        pts = []
        for y in (-self.h*10, self.h*0.5, self.h*11):
            for x in (-self.w*10, self.w*0.5, self.w*11):
                pt = (x, y)
                if self.outCode(pt) != self.Inside:
                    pts.append(pt)
        return pts
    #
    def clip(self, pt0, pt1):
        #return (pt0, pt1)
        oc0 = self.outCode(pt0)
        oc1 = self.outCode(pt1)
        if oc0 != self.Inside and oc1 != self.Inside:
            return None
        #while oc0 != self.Inside or oc1 != self.Inside:
        if oc0 != self.Inside:
            pt0 = self.intersect(pt1, pt0, oc0)
            if pt0 is None: return None
            oc0 = self.outCode(pt0)
        elif oc1 != self.Inside:
            pt1 = self.intersect(pt0, pt1, oc1)
            if pt1 is None: return None
            oc1 = self.outCode(pt1)
        return [pt0, pt1]
    #
    def intersect(self, pt0, pt1, oc):
        dx = pt1[0] - pt0[0]
        dy = pt1[1] - pt0[1]
        if oc & self.Left:
            y = pt0[1] + dy * (self.x0 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x0, y)
        if oc & self.Right:
            y = pt0[1] + dy * (self.x1 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x1, y)
        if oc & self.Top:
            x = pt0[0] + dx * (self.y0 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y0)
        if oc & self.Bottom:
            x = pt0[0] + dx * (self.y1 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y1)
        return None
    #
    def outCode(self, pt):
        oc = 0
        if pt[0] < self.x0:
            oc |= self.Left
        if pt[0] > self.x1:
            oc |= self.Right
        if pt[1] < self.y0:
            oc |= self.Top
        if pt[1] > self.y1:
            oc |= self.Bottom
        return oc
    #

class ao_snap_dialog(QtWidgets.QDialog):
    IMG_SCALES = [50, 100, 200, 300, 500, 1000, 1500, 2000]
    save_state = None
    def __init__(self, parent=None, glyph_scale=1.):
        super(ao_snap_dialog, self).__init__(parent)
        self.glyph_scale = glyph_scale
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        #
        self._dsp = self._defaultDisplaySettings()
        self.qImg = self.emptyImage()
        self.pixmap = None
        self.img_path = None
        self.img_origin = None
        self.img_spacing = None
        self._preview_scale = 0
        #
        self._mute = True
        #
        self.centers = []
        self.voronoi_segments = []
        #
        self._setup_layout()
        self._dsp_dlg = ao_display_settings_dlg(self, contour_settings=False)
        #
        self._dsp_dlg.changed.connect(self._on_display_settings)
        self._mute = False
    #
    def _setup_layout(self):
        view_layout = QtWidgets.QGridLayout()
        self.setLayout(view_layout)
        view_layout.setColumnStretch(0, 0)
        view_layout.setColumnStretch(1, 1)
        #
        ctl_layout = QtWidgets.QGridLayout()
        for idx in range(1,8):
            ctl_layout.setRowStretch(idx, 0)
        ctl_layout.setRowStretch(6, 1)
        view_layout.addLayout(ctl_layout, 0, 0)
        #
        imgPane = QtWidgets.QGroupBox('Preview')
        imgLayout = QtWidgets.QGridLayout()
        imgPane.setLayout(imgLayout)
        view_layout.addWidget(imgPane, 0, 1)
        #
        self.img_lab = QtWidgets.QLabel()
        self.img_lab.setBackgroundRole(QtGui.QPalette.Base)
        self.img_lab.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.scrl = QtWidgets.QScrollArea()
        self.scrl.setBackgroundRole(QtGui.QPalette.Dark)
        self.scrl.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.scrl.setWidget(self.img_lab)
        imgLayout.addWidget(self.scrl, 0, 0)
        #
        sizePane = QtWidgets.QGroupBox('Output Image Options')
        sizeLayout = QtWidgets.QGridLayout()
        sizePane.setLayout(sizeLayout)
        ctl_layout.addWidget(sizePane, 0, 0)
        #
        scaleLab = QtWidgets.QLabel('Scale (%):')
        sizeLayout.addWidget(scaleLab, 0, 0)
        self.comboScale = QtWidgets.QComboBox()
        self.comboScale.setMinimumContentsLength(8)
        self.comboScale.setEditable(True)
        self.comboScale.addItems([str(sc) for sc in self.IMG_SCALES])
        self.comboScale.setCurrentText('200')
        sizeLayout.addWidget(self.comboScale, 0, 1)
        #
        widthLab = QtWidgets.QLabel('Width (pix):')
        sizeLayout.addWidget(widthLab, 1, 0)
        self.txWidth = QtWidgets.QLineEdit()
        self.txWidth.setStyleSheet('QLineEdit {width: 10en;}')
        sizeLayout.addWidget(self.txWidth, 1, 1)
        #
        heightLab = QtWidgets.QLabel('Height (pix):')
        sizeLayout.addWidget(heightLab, 2, 0)
        self.txHeight = QtWidgets.QLineEdit()
        self.txHeight.setStyleSheet('QLineEdit {width: 10en;}')
        sizeLayout.addWidget(self.txHeight, 2, 1)
        #
        poptPane = QtWidgets.QGroupBox('Preview Options')
        ctl_layout.addWidget(poptPane, 1, 0, 1, 2)
        poptLayout = QtWidgets.QGridLayout()
        poptPane.setLayout(poptLayout)
        self.rbFit = QtWidgets.QRadioButton('Fit')
        poptLayout.addWidget(self.rbFit, 0, 0)
        self.rbOne = QtWidgets.QRadioButton('100%')
        poptLayout.addWidget(self.rbOne, 0, 1)
        self.rbTwo = QtWidgets.QRadioButton('200%')
        poptLayout.addWidget(self.rbTwo, 0, 2)
        self.rbFit.setChecked(True)
        #
        spaceLab = QtWidgets.QLabel(' ')
        ctl_layout.addWidget(spaceLab, 2, 0)
        #
        btnLayout = QtWidgets.QGridLayout()
        btnLayout.setColumnStretch(0, 0)
        btnLayout.setColumnStretch(1, 1)
        btnLayout.setColumnStretch(2, 0)
        ctl_layout.addLayout(btnLayout, 3, 0)
        self.btnDisp = QtWidgets.QPushButton('Settings')
        btnLayout.addWidget(self.btnDisp, 0, 0)
        self.btnSave = QtWidgets.QPushButton('Save Image')
        btnLayout.addWidget(self.btnSave, 0, 2)
        #
        self.btnClose = QtWidgets.QPushButton('Close')
        ctl_layout.addWidget(self.btnClose, 7, 0)
        #
        self.comboScale.currentTextChanged.connect(self._onComboScale)
        self.txWidth.textChanged.connect(self._onTxWidth)
        self.txHeight.textChanged.connect(self._onTxHeight)
        #
        self.rbFit.toggled.connect(self._on_preview_scale)
        self.rbOne.toggled.connect(self._on_preview_scale)
        self.rbTwo.toggled.connect(self._on_preview_scale)
        self.btnDisp.clicked.connect(self._onBtnDsp)
        self.btnSave.clicked.connect(self._onBtnSave)
        self.btnClose.clicked.connect(self.close)
    #
    def closeEvent(self, e):
        ao_snap_dialog.save_state = self.p_state
        QtWidgets.QDialog.closeEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        self._mute = True
        self.p_state = ao_snap_dialog.save_state
        self._mute = False
        self._sync_output_size()
        self.resizeEvent(None)
    #
    @property
    def p_state(self):
        return {
            'geometry': self.geometry(),
            'out_scale': self.out_scale,
            'preview_scale': self.preview_scale,
        }
    @p_state.setter
    def p_state(self, st):
        try:
            self.setGeometry(st['geometry'])
            self.out_scale = st['out_scale']
            self.preview_scale = st['preview_scale']
        except Exception:
            geom = QtWidgets.QApplication.primaryScreen().geometry()
            self.resize(geom.width() * 45 // 100, geom.height() * 60 // 100)
            self.move(geom.width() * 18 // 100, geom.height() * 18 // 100)
    #
    def emptyImage(self):
        rgb_data = np.empty(shape=(16, 16, 3), dtype=np.uint8)
        rgb_data[:,:,:] = 0x80
        self.qImg = QtGui.QImage(rgb_data.data, 16, 16, 16*3, QtGui.QImage.Format_RGB888)
        self.img_origin = None
        self.img_spacing = None
    #
    def _on_preview_scale(self):
        if self._mute:
            return
        sc = 0
        if self.rbOne.isChecked():
            sc = 1
        elif self.rbTwo.isChecked():
            sc = 2
        if sc != self._preview_scale:
            self._preview_scale = sc
            self.resizeEvent(None)
            if (sc):
                self.centerImage()
    #
    @property
    def preview_scale(self):
        return self._preview_scale
    @preview_scale.setter
    def preview_scale(self, v):
        if not v in (1, 2): v = 0
        self._preview_scale = v
        if v == 2:
            self.rbTwo.setChecked(True)
        elif v == 1:
            self.rbOne.setChecked(True)
        else:
            self.rbFit.setChecked(True)
    #
    def _sync_output_size(self):
        if not self.isVisible(): return
        sc = self.out_scale
        self._mute = True
        w = int(self.qImg.width()*sc)
        h = int(self.qImg.height()*sc)
        self.txWidth.setText(str(w))
        self.txHeight.setText(str(h))
        self._mute = False
    #
    def _out_scale_valid(self, sc):
        return sc >= 1. and sc <= 10000.
    def _out_size_valid(self, sz):
        return sz > 1
    #
    @property
    def out_scale(self):
        try:
            sc = float(self.comboScale.currentText())
            assert self._out_scale_valid(sc)
        except Exception:
            sc = 100.
            self._mute = True
            self.comboScale.setCurrentText(str(sc))
            self._mute = False
        return sc * 0.01
    @out_scale.setter
    def out_scale(self, sc):
        self.comboScale.setCurrentText(str(int(sc*10000)*0.01))
    #
    @property
    def out_width(self):
        try:
            w = int(self.txWidth.text())
            assert self._out_size_valid(w)
        except Exception:
            w = int(self.out_scale * self.qImg.width())
        return w
    @out_width.setter
    def out_width(self, w):
        self.txWidth.setText(str(w))
    #
    @property
    def out_height(self):
        try:
            h = int(self.txHeight.text())
            assert self._out_size_valid(h)
        except Exception:
            h = int(self.out_scale * self.qImg.height())
        return h
    @out_height.setter
    def out_height(self, h):
        self.txHeight.setText(str(h))
    #
    def _onComboScale(self, v):
        if self._mute: return
        try:
            sc = float(v)
            assert self._out_scale_valid(sc)
            self._sync_output_size()
        except Exception:
            pass
    def _onTxWidth(self, v):
        if self._mute: return
        try:
            w = int(self.txWidth.text())
            assert self._out_size_valid(w)
            self._mute = True
            self.out_scale = float(w) / self.qImg.width()
            self.out_height = int(self.out_scale * self.qImg.height())
            self._mute = False
        except Exception:
            pass
    def _onTxHeight(self, v):
        if self._mute: return
        try:
            h = int(self.txHeight.text())
            assert self._out_size_valid(h)
            self._mute = True
            self.out_scale = float(h) / self.qImg.height()
            self.out_width = int(self.out_scale * self.qImg.width())
            self._mute = False
        except Exception:
            pass
    #
    def _onBtnDsp(self):
        self._dsp_dlg.displaySettings = self._dsp
        self._dsp_dlg.exec_()
    def _on_display_settings(self, dsp):
        self._dsp = dsp
        if self._mute: return
        self.resizeEvent(None)
    #
    def _defaultDisplaySettings(self):
        return {
            'glyph_visibility': False,
            'glyph_size': 6.,
            'glyph_color': '#00ff00',
            
            'voronoi': False,
            'voronoi_width': 1.5,
            'voronoi_color': '#05c4c4',
            
            'interpolation': True,
            'image_visibility': True,
            'background_color': '#000000',
        }
    #
    @property
    def interpolation(self):
        return self._dsp['interpolation']
    @property
    def image_visibility(self):
        return self._dsp['image_visibility']
    @property
    def background_color(self):
        return self._dsp['background_color']
    @property
    def glyph_visibility(self):
        return self._dsp['glyph_visibility']
    @property
    def glyph_size(self):
        return self._dsp['glyph_size']
    @property
    def glyph_color(self):
        return self._dsp['glyph_color']
    @property
    def voronoi(self):
        return self._dsp['voronoi']
    @property
    def voronoi_width(self):
        return self._dsp['voronoi_width']
    @property
    def voronoi_color(self):
        return self._dsp['voronoi_color']
    #
    def setImageData(self, img_path, img_data=None, displaySettings=None, colorInfo=None):
        self.img_path = img_path
        self._dsp = self._defaultDisplaySettings()
        if displaySettings:
            self._dsp.update(displaySettings)
        if not img_path:
            self.qImg = self.emptyImage()
            return
        self.img_origin = None
        self.img_spacing = None
        if isinstance(img_data, sitk.SimpleITK.Image):
            self.img_origin = img_data.GetOrigin()
            self.img_spacing = img_data.GetSpacing()
            img_data = sitk.GetArrayFromImage(img_data)
        elif not isinstance(img_data, np.ndarray):
            img_data = None
        if img_data is None:
            try:
                img_data = imread(img_path)
            except Exception:
                pass
        if img_data is None or len(img_data.shape) < 2:
            self.qImg = self.emptyImage()
            return
        while len(img_data.shape) > 3:
            img_data = img_data[0]
        nc = 1
        w = img_data.shape[1]
        h = img_data.shape[0]
        if len(img_data.shape) == 3:
            nc = img_data.shape[2]
            if nc == 2 or nc > 4:
                img_data = img_data[:,:,0]
                nc = 1
            elif nc == 4:
                img_data = img_data[:,:,0:3]
                nc = 3
        if colorInfo is None:
            if img_data.dtype != np.uint8:
                lmin = np.min(img_data)
                lmax = np.max(img_data)
                if lmax < lmin + 0.001:
                    lmax = lmin + 0.001
                sc = 255. / (lmax - lmin)
                img_data = ((img_data.astype(np.float32) - lmin) * sc).astype(np.uint8)
        else:
            clvl, cwin = colorInfo
            if img_data.dtype == np.uint8:
                shift = 128.
                cwin = 255./cwin
            elif img_data.dtype == np.uint16:
                shift = 32768.
                cwin = 65535./cwin
                clvl /= 256.
            else:
                nrm = 1.
            clvl = 250. - clvl
            img_data = (img_data.astype(np.float32) - shift) * cwin + clvl
            img_data[img_data<0.] = 0.
            img_data[img_data>255.] = 255.
            img_data = img_data.astype(np.uint8)
        if nc != 3:
            rgb_img = np.empty(shape=(h, w, 3), dtype=np.uint8)
            rgb_img[:,:,0] = img_data
            rgb_img[:,:,1] = img_data
            rgb_img[:,:,2] = img_data
        else:
            rgb_img = img_data
        self.qImg = QtGui.QImage(rgb_img.data, w, h, w*3, QtGui.QImage.Format_RGB888)
        self._sync_output_size()
    #
    def setPoints(self, points):
        if self.img_origin and self.img_spacing:
            ox = self.img_origin[0]
            oy = self.img_origin[1]
            sx = self.img_spacing[0]
            sy = self.img_spacing[1]
            self.centers = [(x[0]/sx-ox, x[1]/sy-oy) for x in points]
        else:
            self.centers = [(x[0], x[1]) for x in points]
        self.voronoi_segments = []
                
        if len(self.centers) > 2:
            clip = SegmentClipper((self.qImg.width(), self.qImg.height()))
            annos = self.centers + clip.bnd_points()
            vor = Voronoi(np.array(annos))
            vertices = [(v[0], v[1]) for v in vor.vertices]
            ptis = set()
            for rg in vor.regions:
                if len(rg) < 2: continue
                idx0 = -1
                for idx in rg:
                    if idx >=0 and idx0 >= 0:
                        pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                        ptis.add(pti)
                    idx0 = idx
                idx = rg[0]
                if idx >=0 and idx0 >= 0:
                    pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                    ptis.add(pti)
            #
            for (i0, i1) in ptis:
                pts = clip.clip(vertices[i0], vertices[i1])
                if pts:
                    self.voronoi_segments.append(pts)
    #
    GLYPH_COORD = [(-1, -1), (-1, -5), (1, -5),
            (1, -1), (5, -1), (5, 1),
            (1, 1), (1, 5), (-1, 5),
            (-1, 1), (-5, 1), (-5, -1), ]
    def _scaled_glyph_poly(self, sc):
        sp = 1. if not self.img_spacing else self.glyph_scale/self.img_spacing[0]
        sc = sc * self.glyph_size * 0.1*sp
        return QtGui.QPolygon([QtCore.QPoint(x*sc, y*sc) for x, y in self.GLYPH_COORD])
    #
    def resizeEvent(self, e):
        if not hasattr(self, 'qImg') or self.qImg is None:
            return
        if not self.isVisible():
            return
        sc = self.preview_scale
        if sc == 0:
            qsz = self.scrl.size()
            scx = (qsz.width() - 2) / self.qImg.width()
            sc = (qsz.height() - 2) / self.qImg.height()
            if scx < sc:
                sc = scx
        elif not e is None:
            return
        self.renderImage(sc)
    #
    def generateScaledPixmap(self, sc):
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        
        if self.image_visibility:
            scImg = self.qImg.scaled(int(self.qImg.width()*sc), int(self.qImg.height()*sc),
                    transformMode=QtCore.Qt.SmoothTransformation if self.interpolation else QtCore.Qt.FastTransformation)
            pixmap = QtGui.QPixmap.fromImage(scImg)
            del scImg
        else:
            pixmap = QtGui.QPixmap(int(self.qImg.width()*sc), int(self.qImg.height()*sc))
            color = QtGui.QColor(self.background_color)
            pixmap.fill(color)

        # Draw annotations
        painter = QtGui.QPainter(pixmap)
        # Glyphs
        if self.glyph_visibility:
            glyph = self._scaled_glyph_poly(sc)
            color = QtGui.QColor(self.glyph_color)
            painter.setPen(QtGui.QPen(color, 1, QtCore.Qt.SolidLine))
            painter.setBrush(QtGui.QBrush(color, QtCore.Qt.SolidPattern))
            for x, y in self.centers:
                poly = glyph.translated(x*sc, y*sc)
                painter.drawPolygon(poly)
        # Voronoi diagram
        if self.voronoi:   
            color = QtGui.QColor(self.voronoi_color)
            painter.setPen(QtGui.QPen(color, self.voronoi_width * sc * 0.5, QtCore.Qt.SolidLine))
            for seg in self.voronoi_segments:
                x1, y1 = seg[0]
                x2, y2 = seg[1]
                painter.drawLine(x1*sc, y1*sc, x2*sc, y2*sc)
        #
        painter.end()
        QtWidgets.QApplication.restoreOverrideCursor()
        return pixmap
    #
    def renderImage(self, sc=None):
        if sc is None:
            sc = self.out_scale
        self.pixmap = self.generateScaledPixmap(sc)
        self.img_lab.setPixmap(self.pixmap)
        self.img_lab.resize(self.pixmap.width(), self.pixmap.height())
        self.update()
    #
    def centerImage(self):
        wsz = self.scrl.widget().size()
        vsz = self.scrl.viewport().size()
        if wsz.width() >= vsz.width():
            self.scrl.horizontalScrollBar().setValue((wsz.width() - vsz.width()) // 2)
        if wsz.height() >= vsz.height():
            self.scrl.verticalScrollBar().setValue((wsz.height() - vsz.height()) // 2)
    #
    def _onBtnSave(self):
        if not self.img_path:
            return
        cdir, infn = os.path.split(self.img_path)
        bn, ext = os.path.splitext(infn)
        w = int(self.out_scale * self.qImg.width())
        h = int(self.out_scale * self.qImg.height())
        outfn = f'{bn}-({w},{h}).png'
    
        fpath = os.path.join(cdir, outfn)
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["PNG Images (*.png)", "All files (*.*)"])
        file_dialog.selectNameFilter('')
        file_dialog.setWindowTitle('Save Annotated Image Snapshot')
        file_dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        file_dialog.setWindowFilePath(fpath)
        file_dialog.setDirectory(cdir)
        file_dialog.selectFile(outfn)
    
        if not file_dialog.exec_():
            return
        pkl_filenames = file_dialog.selectedFiles()
        if len(pkl_filenames) < 1:
            return
    
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            pixmap = self.generateScaledPixmap(self.out_scale)
            pixmap.save(pkl_filenames[0], 'PNG')
        except Exception as ex:
            print(ex)
        QtWidgets.QApplication.restoreOverrideCursor()

