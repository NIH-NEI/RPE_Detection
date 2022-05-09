import os, sys

from PyQt5 import QtCore, QtGui, QtWidgets

class AoColorButton(QtWidgets.QPushButton):
    def __init__(self, onchange=None):
        super(AoColorButton, self).__init__()
        self.onchange = onchange
        #
        self.setStyleSheet('margin: 0; padding: 4 4 4 4;')
        self._color = QtGui.QColor(0, 0xFF, 0)
        self._w = 32
        self._h = 32
        #
        self.updateIcon()
        self.clicked.connect(self.onclick)
    #
    def updateIcon(self):
        self.img = QtGui.QImage(self._w, self._h, QtGui.QImage.Format_RGB888)
        self.img.fill(0x000000)
        paint = QtGui.QPainter()
        if paint.begin(self.img):
            paint.setBrush(self._color)
            paint.drawRect(2, 2, self._w-4, self._h-4)
            paint.end()
        pixmap = QtGui.QPixmap.fromImage(self.img)
        self.setIcon(QtGui.QIcon(pixmap))
    #
    @property
    def color(self):
        return self._color
    @color.setter
    def color(self, *v):
        if len(v) > 2:
            self._color = QtGui.QColor(*v)
        else:
            self._color = QtGui.QColor(v[0])
        self.updateIcon()
    #
    def setIconSize(self, w, h):
        self._w = w
        self._h = h
        self.updateIcon()
    #
    def onclick(self):
        color = QtWidgets.QColorDialog.getColor(self.color)
        if color.isValid():
            self.color = color
            if not self.onchange is None:
                self.onchange(self.color)
        #

class ao_display_settings(QtWidgets.QDialog):
    changed = QtCore.pyqtSignal([dict])
    def __init__(self, parent=None, contour_settings=True):
        super(ao_display_settings, self).__init__(parent)
        self.contour_settings = contour_settings
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(False)
        self.setWindowTitle('Display Settings')
        #
        self._mute = True
        #
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(32)
        view_layout.setVerticalSpacing(32)
        self.setLayout(view_layout)
        #
        if self.contour_settings:
            contPane = QtWidgets.QGroupBox('Contour Settings')
            view_layout.addWidget(contPane, 0, 0)
            contLayout = QtWidgets.QGridLayout()
            contLayout.setHorizontalSpacing(32)
            contPane.setLayout(contLayout)
        #
        glyphPane = QtWidgets.QGroupBox('Center Glyph Settings')
        view_layout.addWidget(glyphPane, 0, 1)
        glyphLayout = QtWidgets.QGridLayout()
        glyphLayout.setHorizontalSpacing(32)
        glyphPane.setLayout(glyphLayout)
        #
        voronoiPane = QtWidgets.QGroupBox('Voronoi Settings')
        view_layout.addWidget(voronoiPane, 0, 2)
        voronoiLayout = QtWidgets.QGridLayout()
        voronoiLayout.setHorizontalSpacing(32)
        voronoiPane.setLayout(voronoiLayout)
        #
        imagePane = QtWidgets.QGroupBox('Source Image Settings')
        view_layout.addWidget(imagePane, 1, 0, 1, 3)
        imageLayout = QtWidgets.QGridLayout()
        imageLayout.setColumnStretch(0, 1)
        imageLayout.setColumnStretch(1, 0)
        imageLayout.setColumnStretch(2, 0)
        imageLayout.setColumnStretch(3, 0)
        imageLayout.setHorizontalSpacing(32)
        imagePane.setLayout(imageLayout)
        #
        if self.contour_settings:
            self.cbContVisible = QtWidgets.QCheckBox('Visible', stateChanged=lambda x: self.handleChange())
            contLayout.addWidget(self.cbContVisible, 0, 0, 1, 3)
            lbContWidth = QtWidgets.QLabel('Line Width:')
            contLayout.addWidget(lbContWidth, 1, 0)
            self.spContWidth = QtWidgets.QDoubleSpinBox(valueChanged=lambda x: self.handleChange())
            self.spContWidth.setMinimum(0.5)
            self.spContWidth.setSingleStep(0.5)
            self.spContWidth.setMaximum(25.)
            self.spContWidth.setValue(2.)
            contLayout.addWidget(self.spContWidth, 1, 1, 1, 2)
            lbContColor = QtWidgets.QLabel('Color:')
            contLayout.addWidget(lbContColor, 2, 0)
            self.btContColor = AoColorButton(onchange=lambda x: self.handleChange())
            contLayout.addWidget(self.btContColor, 2, 2)
        #
        self.cbGlyphVisible = QtWidgets.QCheckBox('Visible', stateChanged=lambda x: self.handleChange())
        glyphLayout.addWidget(self.cbGlyphVisible, 0, 0, 1, 3)
        lbGlyphWidth = QtWidgets.QLabel('Size:')
        glyphLayout.addWidget(lbGlyphWidth, 1, 0)
        self.spGlyphWidth = QtWidgets.QDoubleSpinBox(valueChanged=lambda x: self.handleChange())
        self.spGlyphWidth.setMinimum(0.5)
        self.spGlyphWidth.setMaximum(250.)
        self.spGlyphWidth.setSingleStep(0.5)
        self.spGlyphWidth.setValue(4.)
        glyphLayout.addWidget(self.spGlyphWidth, 1, 1, 1, 2)
        lbGlyphColor = QtWidgets.QLabel('Color:')
        glyphLayout.addWidget(lbGlyphColor, 2, 0)
        self.btGlyphColor = AoColorButton(onchange=lambda x: self.handleChange())
        glyphLayout.addWidget(self.btGlyphColor, 2, 2)
        #
        self.cbVoronoiVisible = QtWidgets.QCheckBox('Visible', stateChanged=lambda x: self.handleChange())
        voronoiLayout.addWidget(self.cbVoronoiVisible, 0, 0, 1, 3)
        lbVoronoiWidth = QtWidgets.QLabel('Line Width:')
        voronoiLayout.addWidget(lbVoronoiWidth, 1, 0)
        self.spVoronoiWidth = QtWidgets.QDoubleSpinBox(valueChanged=lambda x: self.handleChange())
        self.spVoronoiWidth.setMinimum(0.5)
        self.spVoronoiWidth.setSingleStep(0.5)
        self.spVoronoiWidth.setMaximum(25.)
        self.spVoronoiWidth.setValue(2.)
        voronoiLayout.addWidget(self.spVoronoiWidth, 1, 1, 1, 2)
        lbVoronoiColor = QtWidgets.QLabel('Color:')
        voronoiLayout.addWidget(lbVoronoiColor, 2, 0)
        self.btVoronoiColor = AoColorButton(onchange=lambda x: self.handleChange())
        voronoiLayout.addWidget(self.btVoronoiColor, 2, 2)
        #
        self.cbPix = QtWidgets.QCheckBox('Pixel Interpolation', stateChanged=lambda x: self.handleChange())
        imageLayout.addWidget(self.cbPix, 0, 0)
        self.cbImageVisible = QtWidgets.QCheckBox('Visible', stateChanged=lambda x: self.handleChange())
        self.cbImageVisible.setChecked(True)
        imageLayout.addWidget(self.cbImageVisible, 0, 1)
        lbBkgColor = QtWidgets.QLabel('Background:')
        imageLayout.addWidget(lbBkgColor, 0, 2)
        self.btBkgColor = AoColorButton(onchange=lambda x: self.handleChange())
        self.btBkgColor.color = '#000000'
        imageLayout.addWidget(self.btBkgColor, 0, 3)
        #
        btnLayout = QtWidgets.QGridLayout()
        btnLayout.setHorizontalSpacing(100)
        view_layout.addLayout(btnLayout, 2, 1, 1, 2)
        self.btnDef = QtWidgets.QPushButton('Restore Defaults')
        btnLayout.addWidget(self.btnDef, 0, 0)
        self.btnOk = QtWidgets.QPushButton('  OK  ')
        btnLayout.addWidget(self.btnOk, 0, 1)
        #
        self.btnOk.clicked.connect(self.close)
        self.btnDef.clicked.connect(self.loadDefaults)
        #
        self.displaySettings = None
        self._mute = False
        #self.setFixedSize(self.size())
    #
    def handleChange(self):
        if not self._mute:
            self.changed.emit(self.displaySettings)
    #
    def loadDefaults(self):
        self.displaySettings = None
        self.changed.emit(self.displaySettings)
    #
    @property
    def displaySettings(self):
        res = {
            'glyph_visibility': self.cbGlyphVisible.isChecked(),
            'glyph_size': self.spGlyphWidth.value(),
            'glyph_color': self.btGlyphColor.color.name(),
            
            'voronoi': self.cbVoronoiVisible.isChecked(),
            'voronoi_width': self.spVoronoiWidth.value(),
            'voronoi_color': self.btVoronoiColor.color.name(),
            
            'interpolation': self.cbPix.isChecked(),
            'image_visibility': self.cbImageVisible.isChecked(),
            'background_color': self.btBkgColor.color.name(),
        }
        if self.contour_settings:
            res.update({
                'contour_visibility': self.cbContVisible.isChecked(),
                'contour_width': self.spContWidth.value(),
                'contour_color': self.btContColor.color.name(),
            })
        return res
    @displaySettings.setter
    def displaySettings(self, o):
        self._mute = True
        if isinstance(o, dict):
            try:
                self.cbGlyphVisible.setChecked(o['glyph_visibility'])
                self.spGlyphWidth.setValue(o['glyph_size'])
                self.btGlyphColor.color = o['glyph_color']
                self.cbVoronoiVisible.setChecked(o['voronoi'])
                self.spVoronoiWidth.setValue(o['voronoi_width'])
                self.btVoronoiColor.color = o['voronoi_color']
                self.cbPix.setChecked(o['interpolation'])
                if self.contour_settings:
                    self.cbContVisible.setChecked(o['contour_visibility'])
                    self.spContWidth.setValue(o['contour_width'])
                    self.btContColor.color = o['contour_color']
                self.cbImageVisible.setChecked(o['image_visibility'])
                self.btBkgColor.color = o['background_color']
            except Exception:
                pass
        else:
            self.cbGlyphVisible.setChecked(not self.contour_settings)
            self.spGlyphWidth.setValue(6.)
            self.btGlyphColor.color = '#00ff00'
            self.cbVoronoiVisible.setChecked(False)
            self.spVoronoiWidth.setValue(1.5)
            self.btVoronoiColor.color = '#05c4c4'
            self.cbPix.setChecked(True)
            self.cbImageVisible.setChecked(True)
            self.btBkgColor.color = '#000000'
            if self.contour_settings:
                self.cbContVisible.setChecked(True)
                self.spContWidth.setValue(2)
                self.btContColor.color = '#00ff00'
        self._mute = False
    #
