"""Dialogs for image viewing, bulk sending and invite links."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout

if __package__:
    from .media import decode_media, safe_filename
else:  # Direct and frozen entry points
    from media import decode_media, safe_filename


class FullScreenImageDialog(QDialog):
    downloadRequested=Signal(dict)
    def __init__(self,pixmap,request,parent=None):
        super().__init__(parent)
        self.original = pixmap
        self.request = request
        self.setWindowTitle("Görsel önizlemesi")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog { background: #0b1017; } QLabel { color: #e8edf5; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(QLabel(safe_filename(decode_media(request["media_json"])["name"])))
        top.addStretch()
        close = QPushButton("Kapat  ×")
        close.clicked.connect(self.reject)
        top.addWidget(close)
        root.addLayout(top)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        root.addWidget(self.image, 1)
        actions = QHBoxLayout()
        self.load_status = QLabel("Tam çözünürlüklü görsel yükleniyor…")
        actions.addWidget(self.load_status)
        actions.addStretch()
        self.download_button = QPushButton("Görseli indir…")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._download)
        actions.addWidget(self.download_button)
        root.addLayout(actions)
        self._scale_image()

    def set_full_resolution(self, image):
        self.original = QPixmap.fromImage(image)
        self.load_status.setText("")
        self._scale_image()

    def _scale_image(self):
        if self.original.isNull() or self.image.size().isEmpty():
            return
        ratio = self.image.devicePixelRatioF()
        pixmap = self.original.scaled(self.image.size() * ratio, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap.setDevicePixelRatio(ratio)
        self.image.setPixmap(pixmap)

    def resizeEvent(self,event):
        super().resizeEvent(event);self._scale_image()
    def _download(self):
        self.downloadRequested.emit(self.request);self.accept()


class BulkPreviewDialog(QDialog):
    def __init__(self,collection,targets,parent=None,initial_message="",initial_files=None):
        super().__init__(parent);self.setWindowTitle("Toplu gönderim önizlemesi");self.resize(650,650);self.collection=collection;self.targets=targets;self.files=[]
        v=QVBoxLayout(self); v.addWidget(QLabel(f"Hedef koleksiyon: {collection['name']} · {len(targets)} sohbet"))
        self.message=QPlainTextEdit();self.message.setPlaceholderText("Gönderilecek duyuru metni…");self.message.setMaximumHeight(130);self.message.setPlainText(initial_message);v.addWidget(self.message)
        row=QHBoxLayout();add=QPushButton("Dosya ekle…");remove=QPushButton("Seçili dosyayı kaldır");row.addWidget(add);row.addWidget(remove);row.addStretch();v.addLayout(row)
        self.files_list=QListWidget();self.files_list.setMaximumHeight(90);v.addWidget(self.files_list);self.files=list(initial_files or [])
        for path in self.files:self.files_list.addItem(f"{Path(path).name} · {Path(path).stat().st_size/1024/1024:.2f} MB" if Path(path).is_file() else Path(path).name)
        add.clicked.connect(self._add_files);remove.clicked.connect(self._remove_file)
        commands=QHBoxLayout();allb=QPushButton("Tümünü seç");none=QPushButton("Seçimi kaldır");commands.addWidget(QLabel("Alıcılar"));commands.addStretch();commands.addWidget(allb);commands.addWidget(none);v.addLayout(commands)
        self.list=QListWidget();v.addWidget(self.list,1)
        for t in targets:
            i=QListWidgetItem(f"{t['title']}  ·  {t['kind']}"+("  ·  gönderim yetkisi yok" if not t['can_send'] else ""));i.setData(Qt.UserRole,t);i.setFlags(i.flags()|Qt.ItemIsUserCheckable);i.setCheckState(Qt.Checked if t['can_send'] else Qt.Unchecked);i.setFlags(i.flags() if t['can_send'] else i.flags()&~Qt.ItemIsEnabled);self.list.addItem(i)
        allb.clicked.connect(lambda:self._check_all(True));none.clicked.connect(lambda:self._check_all(False))
        foot=QHBoxLayout();self.confirm=QPushButton("Gönderimi onayla");self.confirm.setObjectName("primary");cancel=QPushButton("İptal");self.confirm.clicked.connect(self._confirm);cancel.clicked.connect(self.reject);foot.addStretch();foot.addWidget(cancel);foot.addWidget(self.confirm);v.addLayout(foot)
    def _check_all(self,value):
        for i in range(self.list.count()):
            if self.list.item(i).flags()&Qt.ItemIsEnabled:self.list.item(i).setCheckState(Qt.Checked if value else Qt.Unchecked)
    def _add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Dosya seç");
        for p in paths:
            if p not in self.files:self.files.append(p);self.files_list.addItem(f"{Path(p).name} · {Path(p).stat().st_size/1024/1024:.2f} MB")
    def _remove_file(self):
        i=self.files_list.currentRow()
        if i>=0:self.files.pop(i);self.files_list.takeItem(i)
    def _confirm(self):
        targets=[self.list.item(i).data(Qt.UserRole) for i in range(self.list.count()) if self.list.item(i).checkState()==Qt.Checked]
        if not targets:QMessageBox.warning(self,"Alıcı seçilmedi","Gönderim için en az bir sohbet seçin.");return
        if not self.message.toPlainText().strip() and not self.files:QMessageBox.warning(self,"İçerik eksik","Metin yazın veya dosya ekleyin.");return
        confirm=BulkConfirmDialog(targets,self.parent().store,self.message.toPlainText(),self.files,self)
        if confirm.exec()==QDialog.Accepted:self.selected_targets=targets;self.accept()


class BulkConfirmDialog(QDialog):
    def __init__(self,targets,store,message,files,parent=None):
        super().__init__(parent);self.setWindowTitle("Gönderim hedeflerini doğrula");self.resize(820,620);self.setMinimumSize(640,460)
        root=QVBoxLayout(self);root.addWidget(QLabel(f"{len(targets)} Telegram sohbetine gönderilecek. Aşağıdaki hedefleri ve klasör yollarını kontrol edin."))
        root.addWidget(QLabel("Gönderilecek mesaj"));self.message_view=QPlainTextEdit();self.message_view.setReadOnly(True);self.message_view.setPlainText(message or "(Yalnızca ek gönderilecek)");self.message_view.setMaximumHeight(105);root.addWidget(self.message_view)
        names=[Path(path).name for path in files];attachment_label=QLabel("Ekler: "+(" · ".join(names) if names else "Yok"));attachment_label.setWordWrap(True);attachment_label.setToolTip("\n".join(files));root.addWidget(attachment_label)
        root.addWidget(QLabel("Alıcı ve klasör konumu"));self.targets_table=QTableWidget(len(targets),2);self.targets_table.setHorizontalHeaderLabels(["Kişi / grup","Klasör yolu"]);self.targets_table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.targets_table.setSelectionBehavior(QAbstractItemView.SelectRows);self.targets_table.setWordWrap(False);self.targets_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded);self.targets_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded);self.targets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);self.targets_table.setColumnWidth(0,250);self.targets_table.setColumnWidth(1,850);self.targets_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        for row,target in enumerate(targets):
            paths=store.chat_collection_paths(target["peer_id"]);path_text="\n".join(paths) if paths else "Klasörsüz sohbet"
            for col,value in enumerate((target["title"],path_text)):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.targets_table.setItem(row,col,item)
        root.addWidget(self.targets_table,1)
        warning=QLabel("Gönderilen mesajlar geri alınamaz. Başlatıldıktan sonra bekleyen alıcılar Gönderim Geçmişi bölümünden iptal edilebilir.");warning.setWordWrap(True);root.addWidget(warning)
        buttons=QDialogButtonBox();self.cancel_button=buttons.addButton("Geri dön",QDialogButtonBox.RejectRole);self.send_button=buttons.addButton("Gönderimi başlat",QDialogButtonBox.AcceptRole);self.send_button.setObjectName("primary");self.cancel_button.clicked.connect(self.reject);self.send_button.clicked.connect(self.accept);root.addWidget(buttons)


class InviteLinksDialog(QDialog):
    """Editable, copyable folder tree containing the generated Telegram invite links."""
    def __init__(self,entries,parent=None):
        super().__init__(parent);self.setWindowTitle("Davet bağlantıları");self.resize(760,620);self.setMinimumSize(520,380)
        root=QVBoxLayout(self)
        intro=QLabel("Klasör yapısı ve davet bağlantıları. Bağlantı metnini düzenleyip kopyalayabilirsiniz.");intro.setWordWrap(True);root.addWidget(intro)
        self.editor=QPlainTextEdit();self.editor.setObjectName("inviteText");self.editor.setLineWrapMode(QPlainTextEdit.NoWrap);self.editor.setPlainText(self._format_entries(entries));root.addWidget(self.editor,1)
        self.errors=[entry for entry in entries if entry.get("error")]
        self.log_panel=QPlainTextEdit();self.log_panel.setObjectName("inviteLog");self.log_panel.setReadOnly(True);self.log_panel.setMaximumHeight(120)
        self.log_panel.setPlaceholderText("Uyarı veya hata yok.")
        self.log_panel.setPlainText("\n".join(f"{' › '.join(entry.get('path', []))}: {entry['error']}" for entry in self.errors))
        root.addWidget(QLabel("Uyarılar ve işlem sonuçları"));root.addWidget(self.log_panel)
        footer=QHBoxLayout();self.copy_button=QPushButton("Metni kopyala");self.copy_button.setObjectName("primary");self.copy_status=QLabel("");self.copy_status.setObjectName("muted");close=QPushButton("Kapat");footer.addWidget(self.copy_button);footer.addWidget(self.copy_status);footer.addStretch();footer.addWidget(close);root.addLayout(footer)
        self.copy_button.clicked.connect(self._copy);close.clicked.connect(self.accept)
    @staticmethod
    def _format_entries(entries):
        tree={"children":{},"links":[]}
        for entry in entries:
            if entry.get("error"):
                continue
            node=tree
            path=[part for part in entry.get("path",[]) if part] or ["Sohbet"]
            for part in path:
                node=node["children"].setdefault(part,{"children":{},"links":[]})
            node["links"].append(entry.get("link") or "["+(entry.get("error") or "Davet bağlantısı oluşturulamadı")+"]")
        lines=["Aşağıdaki bağlantılardan ilgili topluluğa katılım sağlayabilirsiniz.",""]
        def append(node,depth=0):
            children=list(node["children"].items())
            for index,(label,child) in enumerate(children):
                last=index==len(children)-1
                prefix="   "*depth+("└── " if last else "├── ")
                links=child["links"]
                if links:label+=f'  →  "{links[0]}"'
                lines.append(prefix+label)
                for link in links[1:]:lines.append("   "*(depth+1)+f'└── Davet bağlantısı  →  "{link}"')
                append(child,depth+1)
        append(tree)
        return "\n".join(lines).rstrip()
    def _copy(self):
        QApplication.clipboard().setText(self.editor.toPlainText());self.copy_status.setText("Metin panoya kopyalandı.")
