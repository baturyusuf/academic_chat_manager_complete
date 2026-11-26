"""Desktop update prompts, checks and installer handoff."""
from __future__ import annotations
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

if __package__:
    from . import update_service
    from .version import APP_VERSION, UPDATE_PUBLIC_KEY
else:  # Direct and frozen entry points
    import update_service
    from version import APP_VERSION, UPDATE_PUBLIC_KEY


class UpdateView:
    """Desktop update prompts, checks and installer handoff."""

    def _init_update_view(self):
        self._update = None
        self._update_checking = False
        self._update_busy = False

    def _updates_enabled(self):
        return bool(sys.platform == "win32" and getattr(sys, "frozen", False)
                    and UPDATE_PUBLIC_KEY and (Path(sys.executable).parent / "Updater.exe").is_file())

    async def _check_updates(self):
        if self._update_checking or self._update_busy or not self._updates_enabled():
            return
        self._update_checking = True
        try:
            update = await asyncio.to_thread(update_service.check_update, APP_VERSION, UPDATE_PUBLIC_KEY)
            self._update = update
            self.update_button.setVisible(update is not None)
            if update:
                self.update_button.setText("↑ Güncelleme: v" + update.version)
        except Exception:
            # Offline, malformed or untrusted release: do not interrupt Telegram.
            pass
        finally:
            self._update_checking = False

    def _offer_update(self):
        if self._update is None or self._update_busy:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Yeni sürüm")
        dialog.setTextFormat(Qt.PlainText)
        dialog.setText(f"v{APP_VERSION} → v{self._update.version}\n\n"
                       "Güncelleme indirilecek ve onayınızla yeniden başlatılacaktır.")
        dialog.setDetailedText(self._update.notes or "Sürüm notu yok.")
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dialog.exec() == QMessageBox.Yes:
            asyncio.create_task(self._download_and_install(self._update))

    def _update_can_restart(self):
        return not (self._direct_sends or (self.bulk_task and not self.bulk_task.done())
                    or (self.bulk and self.bulk.current_job)
                    or self.message_input.toPlainText().strip() or self.pending_chat_files
                    or self._fullscreen_preview is not None)

    async def _download_and_install(self, update):
        if self._update_busy:
            return
        self._update_busy = True
        self.update_button.setEnabled(False)
        stage = None
        launched = False
        try:
            base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AcademicChatManager" / "updates"
            base.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix="update-", dir=base))
            loop = asyncio.get_running_loop()
            def progress(current, total):
                loop.call_soon_threadsafe(self.update_button.setText, f"İndiriliyor %{100*current//total}")
            self.update_button.setText("İndiriliyor…")
            await asyncio.to_thread(update_service.download_update, update, stage, progress)
            if not self._update_can_restart():
                QMessageBox.information(self, "Güncelleme", "Aktif gönderimi bitirin ve mesaj taslaklarını kaydedin veya temizleyin; ardından güncellemeyi tekrar başlatın.")
                return
            if QMessageBox.question(self, "Güncelleme hazır", "Güncelle ve yeniden başlat?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
            if not self._update_can_restart():
                return
            app = Path(sys.executable).resolve()
            helper = stage / "Updater.exe"
            shutil.copy2(app.parent / "Updater.exe", helper)
            subprocess.Popen([str(helper), str(os.getpid()), str(app), str(stage)],
                             cwd=str(stage), env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"),
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            launched = True
            self.setEnabled(False)
            self.close()
        except Exception as error:
            QMessageBox.warning(self, "Güncelleme başarısız", str(error))
        finally:
            if not launched:
                if stage is not None:
                    shutil.rmtree(stage, ignore_errors=True)
                self._update_busy = False
                self.update_button.setEnabled(True)
                self.update_button.setText("↑ Güncelleme: v" + update.version)
