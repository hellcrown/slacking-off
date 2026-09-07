# -*- mode: python ; coding: utf-8 -*-
# 摸鱼哨兵打包配置：python -m PyInstaller --clean --noconfirm sentinel.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('models', 'models')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # base 环境里的大件，本项目用不到，防止误打包
        'torch', 'torchvision', 'matplotlib', 'scipy', 'pandas', 'numba',
        'llvmlite', 'skimage', 'gensim', 'h5py', 'tables', 'IPython',
        'jedi', 'pygments', 'playwright', 'PyMuPDF', 'docx', 'pptx',
        'openpyxl', 'PyQtWebEngine', 'PyQt5.QtWebEngine',
        'tkinter', 'unittest', 'pydoc_data',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MoyuSentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
