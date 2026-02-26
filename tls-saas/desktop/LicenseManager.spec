# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

datas = [('Logos', 'Logos')]
binaries = []
hiddenimports = [
    'flet', 'flet_desktop',
    'sqlalchemy', 'sqlalchemy.dialects.sqlite',
]

# Only collect flet_desktop data/binaries (includes the flet.exe runtime)
for pkg in ['flet', 'flet_desktop']:
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hiddenimports += tmp[2]
    except Exception:
        pass

# Massive exclusion list — License Manager only needs flet + sqlite
excludes = [
    'torch', 'torchvision', 'torchaudio', 'transformers', 'whisper',
    'tensorflow', 'keras', 'caffe2',
    'numpy', 'scipy', 'pandas', 'matplotlib', 'PIL', 'Pillow',
    'sklearn', 'scikit-learn', 'scikit-image', 'skimage', 'statsmodels', 'sympy',
    'bokeh', 'plotly', 'altair', 'holoviews', 'panel', 'datashader',
    'xarray', 'dask', 'numba', 'tables', 'h5py', 'pyarrow', 'numexpr',
    'jupyter', 'notebook', 'ipykernel', 'nbformat', 'nbconvert',
    'selenium', 'seleniumbase', 'undetected_chromedriver',
    'speech_recognition', 'pydub', 'imageio_ffmpeg', 'imageio',
    'sphinx', 'docutils', 'alabaster', 'babel',
    'pytest', 'pylint', 'astroid', 'black', 'yapf', 'autopep8',
    'IPython', 'ipython', 'traitlets', 'jedi', 'parso',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy',
    'cv2', 'opencv', 'llvmlite',
    'zmq', 'tornado',
]

a = Analysis(
    ['license_manager.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LicenseManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Logos\\icon_BLACK.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LicenseManager',
)
