import os, sys

from PyQt5 import QtCore, QtWidgets, QtGui

def is_acceptable_key(event):
    kc = event.key()
    mod = event.modifiers()
    if kc == QtCore.Qt.Key_Space and int(mod) == 0:
        # Space to clear
        return True
    if kc == QtCore.Qt.Key_F4 and mod & QtCore.Qt.AltModifier:
        # Exclude Alt+F4 (standard shortcut for closing the program)
        return False
    if kc >= QtCore.Qt.Key_F1 and kc <= QtCore.Qt.Key_F12:
        # Accepted any Fn key regardless of modifiers
        return True
    if (kc >= QtCore.Qt.Key_0 and kc <= QtCore.Qt.Key_9) or (kc >= QtCore.Qt.Key_A and kc <= QtCore.Qt.Key_Z):
        # Any Meta/Alt/Ctrl/Shift + [A..Z,0..9] with at least one of Meta/Alt/Ctrl modifiers
        return mod & QtCore.Qt.ControlModifier or mod & QtCore.Qt.AltModifier or mod & QtCore.Qt.MetaModifier
    return False
#
def key_to_str(event):
    kc = event.key()
    mod = event.modifiers()
    if kc == QtCore.Qt.Key_Space and int(mod) == 0:
        return ''
    parts = []
    if mod & QtCore.Qt.MetaModifier:
        parts.append('Meta')
    if mod & QtCore.Qt.AltModifier:
        parts.append('Alt')
    if mod & QtCore.Qt.ControlModifier:
        parts.append('Ctrl')
    if mod & QtCore.Qt.ShiftModifier:
        parts.append('Shift')
    if kc >= QtCore.Qt.Key_F1 and kc <= QtCore.Qt.Key_F12:
        num = kc - QtCore.Qt.Key_F1 + 1
        parts.append(f'F{num}')
    elif (kc >= QtCore.Qt.Key_0 and kc <= QtCore.Qt.Key_9) or (kc >= QtCore.Qt.Key_A and kc <= QtCore.Qt.Key_Z):
        parts.append(chr(kc))
    else:
        return ''
    return '+'.join(parts)
#
class keyTableWidget(QtWidgets.QTableWidget):
    hotkeyChanged = QtCore.pyqtSignal([int, str])
    def keyPressEvent(self, e):
        row = self.currentRow()
        if row >= 0 and is_acceptable_key(e):
            self.hotkeyChanged.emit(row, key_to_str(e))
        else:
            super(keyTableWidget, self).keyPressEvent(e)
#
_hint = 'Select an item from the list, then press the desired control key combination or space ' + \
    'to clear current shortcut.\n' + \
    'Acceptable key combinations are: Ctrl/Alt/Meta + alpha (A..Z) or number (0..9), ' + \
    'as well as function keys (F1..F12) with or without any modifiers.\n' + \
    'Examples: Ctrl+A, Ctrl+Shift+6, F5, Alt+F8.'
#    
class ao_hotkey_dialog(QtWidgets.QDialog):
    def __init__(self, parent, action_map, default_key_map):
        super(ao_hotkey_dialog, self).__init__(parent)
        self.action_map = action_map
        self.default_key_map = default_key_map
        #
        self.setWindowTitle('Customize Keyboard Shortcuts')
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.gw = geom.width()
        self.gh = geom.height()
        self.resize(self.gw * 56 // 100, self.gh * 60 // 100)

        #
        self.key_map = self.default_key_map.copy()
        self._akeys = sorted(self.action_map.keys())
        #
        view_layout = QtWidgets.QVBoxLayout()
        self.setLayout(view_layout)
        #
        self.keyTable = keyTableWidget(0, 3)
        self.keyTable.setHorizontalHeaderLabels([u'Action', u'Description', u'Shortcut'])
        self.keyTable.setColumnWidth(0, self.gw * 12 // 100)
        self.keyTable.setColumnWidth(1, self.gw * 32 // 100)
        self.keyTable.verticalHeader().setVisible(False)
        self.keyTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.keyTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.keyTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.keyTable.setShowGrid(False)
        view_layout.addWidget(self.keyTable)
        #
        self.keyTable.setRowCount(len(self._akeys))
        for row, act_name in enumerate(self._akeys):
            act = self.action_map[act_name]
            descr = act.statusTip() or act.toolTip()
            if not descr:
                descr = ''
            else:
                descr = descr.split('[')[0]
            keystr = self.key_map.get(act_name, '')
            #print(act_name, ':', act.toolTip(), ':', act.statusTip())
            self.keyTable.setItem(row, 0, QtWidgets.QTableWidgetItem(act_name))
            self.keyTable.setItem(row, 1, QtWidgets.QTableWidgetItem(descr))
            self.keyTable.setItem(row, 2, QtWidgets.QTableWidgetItem(keystr))
        #
        self.hint_lab = QtWidgets.QLabel(_hint)
        view_layout.addWidget(self.hint_lab)
        #
        btn_layout = QtWidgets.QGridLayout()
        view_layout.addLayout(btn_layout)
        btn_layout.setColumnStretch(0, 0)
        btn_layout.setColumnStretch(1, 1)
        btn_layout.setColumnStretch(2, 0)
        btn_layout.setColumnStretch(3, 0)
        self.defButton = QtWidgets.QPushButton('Defaults')
        btn_layout.addWidget(self.defButton, 0, 0)
        self.saveButton = QtWidgets.QPushButton('Save')
        btn_layout.addWidget(self.saveButton, 0, 2)
        self.closeButton = QtWidgets.QPushButton('Close')
        btn_layout.addWidget(self.closeButton, 0, 3)
        #
        self.keyTable.hotkeyChanged.connect(self._onHotkeyChanged)
        self.defButton.clicked.connect(self._restore_defaults)
        self.closeButton.clicked.connect(self.reject)
        self.saveButton.clicked.connect(self._on_save_button)
        #
        self.setResult(0)
    #
    def _onHotkeyChanged(self, row, keystr):
        _key_map = {}
        for act_name, _keystr in self.key_map.items():
            if _keystr == keystr:
                _keystr = ''
            _key_map[act_name] = _keystr
        _key_map[self._akeys[row]] = keystr
        self.update_key_map(_key_map)
    #
    def update_key_map(self, _key_map):
        self.key_map = _key_map.copy()
        for row, act_name in enumerate(self._akeys):
            keystr = self.key_map.get(act_name, '')
            self.keyTable.item(row, 2).setText(keystr)
    #
    def _restore_defaults(self):
        self.update_key_map(self.default_key_map)
    #
    def _on_save_button(self):
        self.accept()
    #
                



