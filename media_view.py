"""Attachment preview, full resolution viewing, and downloads."""
from __future__ import annotations
import asyncio
from pathlib import Path
from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox
from tempfile import TemporaryDirectory

if __package__:
    from .media import decode_media, safe_filename
    from .ui_dialogs import FullScreenImageDialog
else:  # Direct and frozen entry points
    from media import decode_media, safe_filename
    from ui_dialogs import FullScreenImageDialog


class MediaView:
    """Attachment preview, full resolution viewing, and downloads."""

    def _init_media_view(self):
        self._fullscreen_preview = None
        self._image_preview_cache = {}
        self._image_preview_tasks = {}
        self._preview_scan_queued = False

    def _preview_key(self,request):
        return int(request["peer_id"]),int(request["message_id"])

    def _schedule_visible_previews(self):
        if self._preview_scan_queued:return
        self._preview_scan_queued=True;QTimer.singleShot(0,self._queue_visible_previews)

    def _queue_visible_previews(self):
        self._preview_scan_queued=False
        if not hasattr(self,"messages"):return
        viewport=self.messages.viewport();visible=viewport.rect()
        for preview in self.messages.findChildren(QLabel,"imagePreview"):
            if not preview.isVisible():continue
            position=preview.mapTo(viewport,QPoint(0,0))
            if not visible.intersects(QRect(position,preview.size())):continue
            request=preview.property("mediaRequest")
            if request:self._queue_image_preview(request)

    def _queue_image_preview(self,request):
        key=self._preview_key(request)
        if key in self._image_preview_cache:
            self._set_image_preview_labels(key,self._image_preview_cache[key]);return
        current=self._image_preview_tasks.get(key)
        if current and not current.done():return
        try:loop=asyncio.get_running_loop()
        except RuntimeError:return
        task=loop.create_task(self._load_image_preview(request));self._image_preview_tasks[key]=task
        task.add_done_callback(lambda finished,k=key:self._image_preview_tasks.pop(k,None) if self._image_preview_tasks.get(k) is finished else None)

    def _cancel_image_preview_tasks(self):
        for task in tuple(self._image_preview_tasks.values()):
            if not task.done():task.cancel()
        self._image_preview_tasks.clear()

    def _set_image_preview_labels(self,key,result):
        if not hasattr(self,"messages"):return
        for preview in self.messages.findChildren(QLabel,"imagePreview"):
            request=preview.property("mediaRequest")
            if not request or self._preview_key(request)!=key:continue
            if isinstance(result,QPixmap):
                preview.setPixmap(result);preview.setProperty("mediaLoaded",True)
                preview.setToolTip("Görsel önizlemesi · dosyayı kaydetmek için ekin indirme düğmesini kullanın")
            else:preview.setText(str(result))

    async def _load_image_preview(self,request):
        key=self._preview_key(request);service=self.telegram
        if not service or not service.client or not service.client.is_connected():
            result="Telegram'a bağlanınca görsel önizlemesi yüklenir"
        else:
            try:
                data=await service.download_media_bytes(*key)
                if self.telegram is not service:return
                if not data:result="Önizleme kullanılamıyor · aşağıdaki düğmeden indirebilirsiniz"
                else:
                    image=QPixmap()
                    if not image.loadFromData(data):result="Görsel önizlemesi açılamadı"
                    else:result=image.scaled(400,260,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            except asyncio.CancelledError:raise
            except Exception:result="Önizleme yüklenemedi · aşağıdaki düğmeden indirebilirsiniz"
        if self.telegram is not service:return
        self._image_preview_cache[key]=result
        while len(self._image_preview_cache)>64:self._image_preview_cache.pop(next(iter(self._image_preview_cache)))
        self._set_image_preview_labels(key,result)

    def _show_fullscreen_preview(self, preview, request):
        if self._fullscreen_preview is not None:
            return
        dialog = FullScreenImageDialog(preview.pixmap(), request, self)
        self._fullscreen_preview = dialog
        dialog.setModal(True)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.downloadRequested.connect(lambda target: asyncio.create_task(self._download_message(target)))
        service = self.telegram
        task = None
        if service and service.client and service.client.is_connected():
            task = asyncio.create_task(self._load_fullscreen_image(dialog, service, request))
        else:
            dialog.load_status.setText("Tam çözünürlük için Telegram’a bağlanın.")

        def close_preview():
            self._fullscreen_preview = None
            if task and not task.done():
                task.cancel()

        dialog.finished.connect(close_preview)
        dialog.showFullScreen()

    async def _load_fullscreen_image(self, dialog, service, request):
        def read_image(path):
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            return reader.read()

        try:
            with TemporaryDirectory(prefix="acm-image-") as directory:
                path = Path(directory) / "image"
                await service.download_media(*self._preview_key(request), path)
                decoding = asyncio.create_task(asyncio.to_thread(read_image, path))
                try:
                    image = await asyncio.shield(decoding)
                except asyncio.CancelledError:
                    # Let the decoder close the file before Windows removes it.
                    await decoding
                    raise
            if image.isNull() or self.telegram is not service:
                raise ValueError("Tam çözünürlüklü görsel açılamadı")
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._fullscreen_preview is dialog:
                dialog.load_status.setText("Tam çözünürlüklü görsel yüklenemedi.")
        else:
            if self._fullscreen_preview is dialog:
                dialog.set_full_resolution(image)

    async def _download_message(self,m):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():
            QMessageBox.information(self,"Telegram bağlı değil","Dosya indirmek için Telegram hesabını bağlayın.");return
        metadata=decode_media(m.get("media_json"))
        if not metadata or m.get("peer_id") is None or not m.get("message_id"):
            QMessageBox.information(self,"Dosya indirilemiyor","Bu dosya için geçerli bir Telegram mesajı kayıtlı değil.");return
        default_name=safe_filename(metadata["name"])
        path,_=QFileDialog.getSaveFileName(self,"Dosyayı kaydet",default_name)
        if not path:return
        try:
            self.statusBar().showMessage("Dosya indiriliyor…")
            saved=await self.telegram.download_media(m["peer_id"],m["message_id"],path)
            if not saved:raise IOError("Telegram dosyayı döndürmedi")
            self.statusBar().showMessage(f"Kaydedildi: {saved}",6000)
        except Exception as e:
            self.statusBar().showMessage("İndirme başarısız",6000)
            QMessageBox.warning(self,"İndirme başarısız",str(e))
