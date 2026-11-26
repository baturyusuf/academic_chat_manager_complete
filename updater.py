"""Detached Windows update helper; runs from a staging directory."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime

from update_service import INSTALLER, MANIFEST, verify_manifest, verify_package
from version import APP_VERSION, UPDATE_PUBLIC_KEY


def wait_for_parent(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # process already exited
            return
        raise OSError("Unable to wait for application")
    try:
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise TimeoutError("Application did not exit")
    finally:
        kernel.CloseHandle(handle)


def backup_database():
    source = Path(os.environ["APPDATA"]) / "AcademicChatManager" / "academic_chat_manager.sqlite3"
    if source.is_file():
        dest = source.parent / "backups" / ("pre-update-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
        dest.parent.mkdir(exist_ok=True)
        with sqlite3.connect(source) as original, sqlite3.connect(dest) as backup:
            original.backup(backup)


def main():
    pid, app_path, stage_path = sys.argv[1:]
    app, stage = Path(app_path), Path(stage_path)
    parent_exited = False
    try:
        wait_for_parent(int(pid))
        parent_exited = True
        update = verify_manifest((stage / MANIFEST).read_bytes(), UPDATE_PUBLIC_KEY, APP_VERSION)
        installer = stage / INSTALLER
        verify_package(installer, update)
        backup_database()
        # Do not leak PyInstaller's temporary DLL search directory into native children.
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        result = subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                 "/NORESTART", "/SP-", "/NOCLOSEAPPLICATIONS",
                                 f"/DIR={app.parent}", f"/LOG={stage / 'install.log'}"], env=env)
        if result.returncode != 0:
            raise RuntimeError(f"Kurulum çıkış kodu: {result.returncode}")
        installer.unlink(missing_ok=True)
    except Exception as error:
        ctypes.windll.user32.MessageBoxW(None, f"Güncelleme tamamlanamadı: {error}\nKayıt: {stage}", "Akademik Sohbet Yöneticisi", 0x10)
    finally:
        if parent_exited and app.is_file():
            subprocess.Popen([str(app)], cwd=str(app.parent), env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))


if __name__ == "__main__":
    main()
