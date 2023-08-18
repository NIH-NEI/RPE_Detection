# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['__main__.py'],
             pathex=['.'],
             binaries=[],
             datas=[ ('./model_weights', './model_weights'),
                 ('./Icons/*', './Icons'),  ('./Help/*', './Help') ],
             hiddenimports=['vtkmodules', 'vtkmodules.all', 'vtkmodules.qt.QVTKRenderWindowInteractor',
                 'vtkmodules.util','vtkmodules.util.numpy_support'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['matplotlib', 'matplotlib.tests', 'PyQt4', 'PySide', '_tkinter',
                       'PyQt5.QtPrintSupport', 'PyQt5.QtMultimedia', 'PyQt5.QtBluetooth'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='RPE_Detection',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          icon='Icons\\RPE_Detection256x256.ico',
          runtime_tmpdir=None,
          console=False)
