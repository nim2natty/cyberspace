# PyInstaller recipe used by the cross-platform GitHub release workflow.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for package in ("cyberspace", "keyring", "playwright", "pydantic", "typer", "rich"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(["cyberspace/__main__.py"], pathex=["."], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=["pytest"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="cyberspace",
          console=True, strip=False, upx=False)