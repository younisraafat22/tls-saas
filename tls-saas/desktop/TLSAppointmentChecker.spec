# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [
    ('.env', '.'),
    ('.env.example', '.'),
    ('Logos', 'Logos'),
    ('version.json', '.'),
    ('TERMS_AND_DISCLAIMER.md', '.'),
]

binaries = []

hiddenimports = [
    # Flet framework (GUI)
    'flet', 'flet.core', 'flet_core', 'flet_desktop',
    # Browser automation
    'seleniumbase', 'undetected_chromedriver',
    'selenium', 'selenium.webdriver', 'selenium.webdriver.chrome',
    'selenium.webdriver.chrome.options', 'selenium.webdriver.chrome.service',
    # Database
    'sqlalchemy', 'sqlalchemy.ext.declarative', 'sqlalchemy.orm',
    # Audio CAPTCHA solving
    'speech_recognition', 'pydub', 'imageio_ffmpeg',
    # Encryption & auth
    'bcrypt', 'cryptography', 'cryptography.fernet',
    # Notifications & utilities
    'plyer', 'plyer.platforms.win', 'plyer.platforms.win.notification',
    'dotenv', 'requests', 'urllib3', 'pyperclip',
]

# Only collect data for packages that actually need bundled assets
for pkg in ['flet', 'flet_core', 'flet_desktop', 'seleniumbase', 'imageio_ffmpeg']:
    try:
        tmp = collect_all(pkg)
        datas += tmp[0]
        binaries += tmp[1]
        hiddenimports += tmp[2]
    except Exception:
        pass

# Collect speech_recognition data
try:
    tmp = collect_data_files('speech_recognition')
    datas += tmp
except Exception:
    pass

# Massive exclusion list - these are NOT used by the app
excludes = [
    # ML/AI frameworks (whisper was never used - this was the 800MB bloat!)
    'torch', 'torchvision', 'torchaudio', 'transformers', 'whisper',
    'tensorflow', 'keras', 'caffe2',
    # Scientific computing (not needed)
    'numpy.core._dotblas', 'scipy', 'pandas', 'matplotlib',
    'sklearn', 'scikit-learn', 'statsmodels', 'sympy',
    # Data tools (not needed)
    'bokeh', 'plotly', 'altair', 'holoviews', 'panel', 'datashader',
    'xarray', 'dask', 'numba', 'tables', 'h5py', 'pyarrow',
    # Jupyter/notebook (not needed)
    'notebook', 'jupyterlab', 'jupyter', 'ipython', 'ipykernel',
    'nbconvert', 'nbformat', 'ipywidgets',
    # Qt (not needed - Flet uses its own web renderer)
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy',
    # Image processing (not needed)
    'skimage', 'scikit-image', 'imageio', 'PIL', 'Pillow',
    # AWS/Cloud (not needed - botocore is 97MB!)
    'botocore', 'boto3', 'awscli', 's3transfer',
    # Documentation tools (not needed)
    'sphinx', 'docutils', 'alabaster',
    # Dev tools (not needed)
    'black', 'mypy', 'astroid', 'pylint', 'isort',
    'yapf', 'yapf_third_party', 'blib2to3',
    'jedi', 'parso',
    # Other heavy packages not used
    'astropy', 'nltk', 'spacy', 'gensim',
    'openpyxl', 'xlrd', 'lxml',
    'distributed', 'tornado',
    'pytest', 'unittest', 'doctest',
    'tkinter', 'tk', '_tkinter',
    'timm', 'datasets', 'huggingface_hub',
    'pyviz_comms', 'intake',
    # Numpy MKL (will use OpenBLAS or basic numpy instead)
    'numpy.core._dotblas',
]

a = Analysis(
    ['main.py'],
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

# Remove MKL DLLs (620+ MB!) - numpy works fine without them for this app
import re
a.binaries = [b for b in a.binaries if not re.match(r'mkl_', b[0].lower())]
a.binaries = [b for b in a.binaries if not re.match(r'libiomp', b[0].lower())]

# Remove other unnecessary large binaries
exclude_dlls = ['omptarget', 'mkl_blacs', 'mkl_scalapack']
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in exclude_dlls)]

pyz = PYZ(a.pure)

# Use onedir mode (folder) - more reliable for Flet apps
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TLSAppointmentChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # GUI app - no console window!
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Logos/icon_BLACK.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TLSAppointmentChecker',
)
