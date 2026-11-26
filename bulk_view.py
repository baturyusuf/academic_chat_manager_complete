"""Bulk send, job history, and recipient controls."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTableWidget, QVBoxLayout, QWidget

if __package__:
    from .media import bulk_attachment_cards, format_size
    from .messaging import BulkSender
    from .ui_common import _format_local_datetime, _icon_button
    from .ui_dialogs import BulkPreviewDialog
    from .ui_widgets import HistoryTableItem
else:  # Direct and frozen entry points
    from media import bulk_attachment_cards, format_size
    from messaging import BulkSender
    from ui_common import _format_local_datetime, _icon_button
    from ui_dialogs import BulkPreviewDialog
    from ui_widgets import HistoryTableItem


class BulkView:
    """Bulk send, job history, and recipient controls."""

    def _init_bulk_view(self):
        self.bulk = None
        self.bulk_task = None
        self._bulk_pasted_files = set()

    def _history_page(self):
        p=QWidget();v=QVBoxLayout(p);h=QHBoxLayout();h.addWidget(QLabel("Gönderim geçmişi",objectName="sectionTitle"));h.addStretch();self.retry_btn=QPushButton("Başarısızları yeniden dene");self.retry_btn.clicked.connect(self.retry_failed);h.addWidget(self.retry_btn);self.cancel_history_job_btn=QPushButton("Seçili işi iptal et");self.cancel_history_job_btn.clicked.connect(self.cancel_selected_history_job);h.addWidget(self.cancel_history_job_btn);b=_icon_button("refresh","Yenile");b.clicked.connect(self.refresh_history);h.addWidget(b);v.addLayout(h)
        self.history=QTableWidget(0,7);self.history.setHorizontalHeaderLabels(["Tarih","Koleksiyon","Durum","Başarılı","Toplam","Mesaj","Ekler"]);header=self.history.horizontalHeader();header.setSectionResizeMode(QHeaderView.Interactive);header.setStretchLastSection(False);header.setMinimumSectionSize(90);self.history.setColumnWidth(0,170);self.history.setColumnWidth(1,260);self.history.setColumnWidth(2,110);self.history.setColumnWidth(3,90);self.history.setColumnWidth(4,90);self.history.setColumnWidth(5,320);self.history.setColumnWidth(6,200);self.history.setSortingEnabled(True);self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded);self.history.setSelectionBehavior(QAbstractItemView.SelectRows);v.addWidget(self.history,1)
        self.target_detail=QListWidget();self.target_detail.setMaximumHeight(200);self.target_detail.setSelectionMode(QAbstractItemView.SingleSelection);v.addWidget(QLabel("Alıcı sonuçları"));v.addWidget(self.target_detail);self.cancel_history_target_btn=QPushButton("Seçili bekleyen alıcıyı iptal et");self.cancel_history_target_btn.clicked.connect(self.cancel_selected_history_target);v.addWidget(self.cancel_history_target_btn);self.history_download_btn=QPushButton("Gönderilen dosyayı indir…");self.history_download_btn.setEnabled(False);self.history_download_btn.clicked.connect(self._download_history_attachment);v.addWidget(self.history_download_btn);self.history.itemSelectionChanged.connect(self._history_selected);return p

    def _bulk_page(self):
        p=QWidget();v=QVBoxLayout(p);v.addWidget(QLabel("Toplu mesajlaşma",objectName="sectionTitle"));v.addWidget(QLabel("Bir koleksiyon seçip alıcıları inceleyin. Mesajlar yalnızca her bir sohbet için gönderim onayından sonra gönderilir."));self.bulk_collection_combo=QComboBox();self.bulk_collection_combo.currentIndexChanged.connect(self._bulk_collection_changed);v.addWidget(self.bulk_collection_combo);self.bulk_recipients=QListWidget();v.addWidget(self.bulk_recipients,1);b=QPushButton("Mesaj ve dosya gönder…");b.setObjectName("primary");b.clicked.connect(self.start_bulk);v.addWidget(b);self.cancel_job_btn=QPushButton("Bekleyen işleri iptal et");self.cancel_job_btn.clicked.connect(self.cancel_bulk);v.addWidget(self.cancel_job_btn);return p

    def refresh_bulk_collections(self):
        if not hasattr(self,"bulk_collection_combo"):return
        current=self.bulk_collection_combo.currentData();self.bulk_collection_combo.blockSignals(True);self.bulk_collection_combo.clear()
        for c in self.store.collections():self.bulk_collection_combo.addItem(c['name'],c['id'])
        idx=self.bulk_collection_combo.findData(current if current is not None else self.current_collection)
        if idx>=0:self.bulk_collection_combo.setCurrentIndex(idx)
        self.bulk_collection_combo.blockSignals(False);self._bulk_collection_changed()

    def _bulk_collection_changed(self,*args):
        if not hasattr(self,"bulk_recipients"):return
        self.bulk_recipients.clear();cid=self.bulk_collection_combo.currentData()
        if cid is None:return
        for r in self.store.collection_chats(int(cid),True):self.bulk_recipients.addItem(f"{r['title']}  ·  {r['kind']}"+("  ·  gönderim yetkisi yok" if not r['can_send'] else ""))

    def start_bulk(self,cid=None):
        cid=cid if cid is not None else self.bulk_collection_combo.currentData()
        if cid is None:QMessageBox.information(self,"Klasör seçin","Önce bir koleksiyon oluşturun.");return
        return self._start_bulk(collection_ids=[int(cid)])

    def _start_bulk(self,collection_ids=None,direct_peer_ids=None,preserve_view=False,initial_message="",initial_files=None):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():QMessageBox.warning(self,"Telegram bağlı değil","Toplu gönderim için önce Telegram hesabını bağlayın.");return
        collection_ids=list(dict.fromkeys(int(x) for x in (collection_ids or [])))
        direct_peer_ids=list(dict.fromkeys(int(x) for x in (direct_peer_ids or [])))
        targets_by_peer={}
        for cid in collection_ids:
            for target in self.store.collection_chats(cid,True):targets_by_peer[int(target['peer_id'])]=target
        for peer_id in direct_peer_ids:
            target=self.store.chat(peer_id)
            if target and target['available'] and not target['hidden']:targets_by_peer[peer_id]=target
        targets=sorted(targets_by_peer.values(),key=lambda row:row['title'].casefold())
        if not targets:QMessageBox.information(self,"Alıcı yok","Seçili klasörlerde veya sohbetlerde gönderilebilir alıcı bulunamadı.");return
        collections={c['id']:c for c in self.store.collections()};names=[" › ".join(self.store.collection_path(cid)) for cid in collection_ids if cid in collections]
        label=" + ".join(names) if names else "Seçili sohbetler"
        collection={"name":label}
        dlg=BulkPreviewDialog(collection,targets,self,initial_message,initial_files)
        if dlg.exec()!=QDialog.Accepted:return
        try:
            self._bulk_pasted_files.update(path for path in dlg.files if path in self._pasted_clipboard_files)
            primary=collection_ids[0] if collection_ids else None
            sender=BulkSender(self.store,self.telegram);job=sender.prepare_job(primary,dlg.message.toPlainText(),dlg.files,dlg.selected_targets,collection_ids=collection_ids);self.bulk=sender;self.refresh_history()
            if preserve_view:
                if collection_ids:self._render_collection_history()
                self.message_input.clear();self._clear_chat_files();self._clear_reply();self.message_input.setPlaceholderText("Seçili klasör ve sohbetlere gönderilecek mesaj…")
            else:self.navigate("history")
            self.bulk_task=asyncio.create_task(self._run_bulk(job,dlg.selected_targets,dlg.message.toPlainText(),dlg.files,preserve_view))
        except Exception as e:QMessageBox.warning(self,"Gönderim hazırlanamadı",str(e))

    async def _run_bulk(self,job,targets,message,files,preserve_view=False):
        try:await self.bulk.run(job,targets,message,files)
        finally:
            self.refresh_history()
            if preserve_view and self.context_mode in ("collection","selection"):self._render_collection_history()
            self.statusBar().showMessage("Gönderim kuyruğu tamamlandı. Ayrıntılı durum Gönderim Geçmişi bölümünde.",8000)

    def cancel_bulk(self):
        if self.bulk:self.bulk.cancel();self.statusBar().showMessage("Bekleyen hedefler iptal edilecek; gönderilmiş mesajlar geri alınamaz.",7000)

    def refresh_history(self):
        if not hasattr(self,"history"):return
        jobs=self.store.jobs();self.history.setSortingEnabled(False);self.history.setRowCount(0);self._history_jobs=jobs;collections={c['id']:c for c in self.store.collections()}
        for j in jobs:
            row=self.history.rowCount();self.history.insertRow(row);ids=self.store.job_collection_ids(j['id']);coll=" + ".join(" › ".join(self.store.collection_path(cid)) for cid in ids if cid in collections) or "Seçili sohbetler"
            try:files=json.loads(j.get('files_json') or '[]')
            except (TypeError,json.JSONDecodeError):files=[]
            message=j.get('message') or "(Yalnızca ek gönderildi)";attachment_names=" · ".join(Path(path).name for path in files) or "—"
            values=[_format_local_datetime(j['created_at']),coll,j['status'],j['sent'] or 0,j['total'] or 0,message,attachment_names]
            for col,val in enumerate(values):
                item=HistoryTableItem(val,j['id'])
                if col==6 and files:item.setToolTip("\n".join(files))
                self.history.setItem(row,col,item)
        self.history.setSortingEnabled(True)
        if self.history.rowCount():self.history.selectRow(0)

    def _history_selected(self):
        items=self.history.selectedItems()
        if not items:
            self.target_detail.clear();self.cancel_history_job_btn.setEnabled(False);self.cancel_history_target_btn.setEnabled(False);self.history_download_btn.setEnabled(False);return
        jobid=items[0].data(Qt.UserRole)
        if not jobid:return
        self.target_detail.clear();targets=self.store.job_targets(jobid);active=any(t['status'] in ('pending','sending') for t in targets);self.cancel_history_job_btn.setEnabled(active)
        for t in targets:
            item=QListWidgetItem(f"{t['peer_title']}  ·  {t['status']}"+(f"  ·  {t['error']}" if t['error'] else ""));item.setData(Qt.UserRole,(jobid,t['peer_id'],t['status']));self.target_detail.addItem(item)
        self.cancel_history_target_btn.setEnabled(any(t['status']=='pending' for t in targets))
        self.history_download_btn.setEnabled(bool(self._history_downloadable(jobid,targets)))

    def _history_downloadable(self,jobid,targets=None):
        job=next((job for job in self._history_jobs if job["id"]==jobid),None)
        if not job:return []
        try:files=json.loads(job.get("files_json") or "[]")
        except (TypeError,ValueError):return []
        return [card for card in bulk_attachment_cards(files,self.store.job_targets(jobid) if targets is None else targets) if card.get("message_id")]

    def _download_history_attachment(self):
        items=self.history.selectedItems()
        if not items:return
        cards=self._history_downloadable(items[0].data(Qt.UserRole))
        if not cards:return
        if len(cards)>1:
            labels=[f"{i+1}. {card['name']} · {format_size(card.get('size'))}" for i,card in enumerate(cards)]
            label,ok=QInputDialog.getItem(self,"Dosya indir","Kaydedilecek dosya:",labels,0,False)
            if not ok:return
            card=cards[labels.index(label)]
        else:card=cards[0]
        asyncio.create_task(self._download_message({"peer_id":card["peer_id"],"message_id":card["message_id"],"media_json":json.dumps(card,ensure_ascii=False)}))

    def cancel_selected_history_job(self):
        items=self.history.selectedItems()
        if not items:return
        jobid=items[0].data(Qt.UserRole);targets=self.store.job_targets(jobid)
        if not any(t['status'] in ('pending','sending') for t in targets):QMessageBox.information(self,"İptal edilecek hedef yok","Bu işte iptal edilebilir bekleyen alıcı yok.");return
        if QMessageBox.question(self,"Gönderimi iptal et","Bu gönderimdeki henüz iletilmemiş alıcılar iptal edilsin mi? O sırada Telegram'a aktarılmakta olan mesaj tamamlanabilir.",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if self.bulk and self.bulk.current_job==jobid:self.bulk.cancel()
        self.store.cancel_job(jobid);self.refresh_history();self.statusBar().showMessage("Bekleyen alıcılar iptal edildi.",6000)

    def cancel_selected_history_target(self):
        item=self.target_detail.currentItem()
        if not item:return
        jobid,peer_id,status=item.data(Qt.UserRole)
        if status!='pending':QMessageBox.information(self,"Alıcı beklemiyor","Yalnızca sırada bekleyen alıcılar iptal edilebilir.");return
        if QMessageBox.question(self,"Alıcıyı iptal et",f"{item.text().split('  ·  ')[0]} için gönderim iptal edilsin mi?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if not self.store.cancel_target(jobid,peer_id):QMessageBox.information(self,"Alıcı başlatılmış","Bu alıcı artık beklemede değil; gönderim başlamış olabilir.");return
        self.refresh_history();self.statusBar().showMessage("Seçili alıcı iptal edildi.",6000)

    def retry_failed(self):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():QMessageBox.warning(self,"Telegram bağlı değil","Yeniden denemeden önce hesabı bağlayın.");return
        items=self.history.selectedItems()
        if not items:return
        jobid=items[0].data(Qt.UserRole);job=next((j for j in self.store.jobs() if j['id']==jobid),None)
        if not job:return
        retry=[t for t in self.store.job_targets(jobid) if t['status'] in ('failed','flood_wait')]
        if not retry:QMessageBox.information(self,"Yeniden denenecek hedef yok","Bu gönderimde başarısız veya FloodWait nedeniyle bekleyen hedef bulunamadı.");return
        if QMessageBox.question(self,"Yeniden gönderimi onayla",f"{len(retry)} başarısız hedefe yeniden gönderilsin mi? Daha önce gönderilen hedefler atlanacak.")!=QMessageBox.Yes:return
        targets=[{"peer_id":t['peer_id'],"title":t['peer_title'],"can_send":1} for t in retry]
        files=json.loads(job['files_json'] or '[]');sender=BulkSender(self.store,self.telegram);self.bulk=sender;self.bulk_task=asyncio.create_task(self._run_bulk(jobid,targets,job['message'],files))
