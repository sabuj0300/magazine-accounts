# PyInstaller recipe:  pyinstaller MagazineAccounts.spec   -> dist/MagazineAccounts(.exe)
import sys
a = Analysis(
    ["desktop.py"],
    pathex=["."],
    datas=[("templates", "templates"), ("static", "static")],
    hiddenimports=["app", "db", "version", "waitress", "openpyxl", "sqlite3", "tkinter"],
    excludes=["psycopg", "psycopg_binary", "psycopg_c", "access_parser", "import_access", "pytest", "numpy", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="MagazineAccounts",
    console=False,                 # no black window; the small control window is the program's face
    upx=False,
)
