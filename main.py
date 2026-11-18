from __future__ import annotations
import asyncio, json, mimetypes, os, sys, traceback
from pathlib import Path
import certifi
if os.name=="nt" or not os.environ.get("SSL_CERT_FILE") or not Path(os.environ["SSL_CERT_FILE"]).is_file():
    os.environ["SSL_CERT_FILE"]=certifi.where()
from datetime import datetime
from PySide6.QtCore import Qt, QSettings, QSize, QRect, Signal, QMimeData, QTimer, QItemSelectionModel
from PySide6.QtGui import QAction, QFont, QPixmap, QColor, QDrag, QIcon, QPalette, QKeySequence, QShortcut, QPainter
from PySide6.QtWidgets import *
from qasync import QEventLoop, asyncSlot
try:  # package import for tests; direct imports for the frozen desktop entry point
    from .storage import Store, app_data_dir
    from .telegram_service import TelegramService
    from .messaging import BulkSender
    from . import security
except ImportError:
    from storage import Store, app_data_dir
    from telegram_service import TelegramService
    from messaging import BulkSender
    import security

APP_DIR=Path(__file__).parent
PREFS=QSettings("RumeliAcademic","AcademicChatManager")
TREE_NODE_KIND_ROLE=Qt.UserRole+1
TREE_OWNER_COLLECTION_ROLE=Qt.UserRole+2
def _mix_color(foreground: str, background: str, amount: float) -> str:
    fg, bg = QColor(foreground), QColor(background)
    channels = [round(bg.getRgb()[i] * (1 - amount) + fg.getRgb()[i] * amount) for i in range(3)]
    return QColor(*channels).name()

def _theme_stylesheet(dark: bool, accent: str) -> str:
    highlight = _mix_color(accent, "#ffffff", .42) if dark else accent
    accent_text = "#202938" if QColor(accent).lightness() > 155 else "#ffffff"
    if dark:
        c = dict(window="#151922", surface="#1d232e", raised="#252c38", input="#202733",
                 text="#e8edf5", muted="#a1adbd", border="#343d4c", hover="#2b3442",
                 selection=_mix_color(accent, "#252c38", .28), selected_text="#ffffff",
                 track="#343d4c", status="#1d232e")
    else:
        c = dict(window="#f3f5f9", surface="#ffffff", raised="#f7f8fb", input="#f7f8fb",
                 text="#202938", muted="#687589", border="#e2e7ef", hover="#eef1f6",
                 selection=_mix_color(accent, "#ffffff", .13), selected_text="#202938",
                 track="#e2e7ef", status="#ffffff")
    return f"""
    QMainWindow,QWidget#root{{background:{c['window']};color:{c['text']}}}
    QWidget{{color:{c['text']}}}
    QFrame#topbar,QFrame#sidebar,QFrame#panel,QFrame#conversation,QFrame#compose{{background:{c['surface']};border:1px solid {c['border']};border-radius:14px}}
    QDialog,QMessageBox,QInputDialog{{background:{c['surface']};color:{c['text']}}}
    QDialog QLabel,QMessageBox QLabel,QInputDialog QLabel{{color:{c['text']}}}
    QDialogButtonBox QPushButton{{min-width:74px}}
    QStackedWidget#centerStack{{background:transparent}}
    QScrollArea#settingsPage,QScrollArea#settingsPage QWidget#qt_scrollarea_viewport,QWidget#settingsInner{{background:{c['surface']}}}
    QFrame#chatHeader{{background:{c['surface']};border:0;border-bottom:1px solid {c['border']};border-top-left-radius:14px;border-top-right-radius:14px}}
    QLabel#brandTitle,QLabel#sectionTitle{{font-weight:700;color:{c['text']}}}
    QLabel#brandSubtitle,QLabel#muted{{color:{c['muted']}}}
    QPushButton{{border:0;border-radius:9px;background:transparent;padding:8px 11px;text-align:left;color:{c['text']}}}
    QPushButton:hover{{background:{c['hover']}}}
    QPushButton[active="true"],QPushButton#primary,QPushButton#primary:checked{{background:{accent};color:{accent_text};font-weight:600}}
    QPushButton#primary:hover{{background:{_mix_color(accent, '#000000' if dark else '#ffffff', .88)}}}
    QLineEdit,QComboBox,QSpinBox,QPlainTextEdit{{background:{c['input']};color:{c['text']};border:1px solid {c['border']};border-radius:10px;padding:8px 10px;selection-background-color:{accent};selection-color:#ffffff}}
    QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus{{border:1px solid {accent}}}
    QListWidget,QTreeWidget,QTableWidget{{border:0;background:transparent;color:{c['text']};outline:0;alternate-background-color:{c['raised']}}}
    QListWidget::item{{padding:9px 8px;border-bottom:1px solid {c['border']};border-radius:8px}}
    QListWidget::item:selected,QTreeWidget::item:selected,QTableWidget::item:selected{{background:{c['selection']};color:{c['selected_text']}}}
    QTreeWidget::item{{padding:5px}}
    QGroupBox{{background:{c['surface']};border:1px solid {c['border']};border-radius:12px;margin-top:14px;padding:14px 12px 12px;font-weight:650}}
    QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 4px;color:{c['text']}}}
    QHeaderView,QHeaderView::viewport{{background:{c['raised']};color:{c['text']}}}
    QHeaderView::section{{background:{c['raised']};color:{c['text']};border:0;border-bottom:1px solid {c['border']};padding:7px 9px;font-weight:600}}
    QTableCornerButton::section{{background:{c['raised']};border:0}}
    QSlider::groove:horizontal{{height:5px;background:{c['track']};border-radius:2px}}
    QSlider::handle:horizontal{{background:{accent};width:15px;margin:-5px 0;border-radius:7px}}
    QTabWidget::pane{{border:0}}
    QTabBar::tab{{background:{c['raised']};color:{c['muted']};padding:10px 16px;border-radius:9px 9px 0 0;margin-right:4px}}
    QTabBar::tab:selected{{background:{accent};color:{accent_text};font-weight:600}}
    QSplitter::handle{{background:{c['border']};width:5px;margin:0 2px;border-radius:2px}}
    QSplitter::handle:hover{{background:{accent}}}
    QStatusBar{{background:{c['status']};color:{c['muted']};border-top:1px solid {c['border']}}}
    QMenu{{background:{c['surface']};color:{c['text']};border:1px solid {c['border']};padding:4px}}
    QMenu::item{{padding:7px 22px;border-radius:5px}}
    QMenu::item:selected{{background:{c['selection']};color:{c['selected_text']}}}
    QFrame#incomingBubble{{background:{c['surface']};border:1px solid {c['border']};border-radius:13px}}
    QFrame#outgoingBubble{{background:{_mix_color(accent, c['surface'], .13 if not dark else .32)};border:1px solid {_mix_color(accent, c['border'], .25)};border-radius:13px}}
    QLabel#messageSender{{font-weight:650;color:{highlight}}}
    QLabel#messageText{{color:{c['text']}}}
    QLabel#messageTime{{color:{c['muted']}}}
    QListWidget#messages::item{{border:0;background:transparent;padding:0}}
    QScrollBar:vertical{{background:transparent;width:10px;margin:3px}}
    QScrollBar::handle:vertical{{background:{c['border']};border-radius:5px;min-height:30px}}
    QScrollBar::handle:vertical:hover{{background:{c['muted']}}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0}}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical,QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{{background:transparent}}
    QScrollBar:horizontal{{background:transparent;height:10px;margin:3px}}
    QScrollBar::handle:horizontal{{background:{c['border']};border-radius:5px;min-width:30px}}
    QScrollBar::handle:horizontal:hover{{background:{c['muted']}}}
    QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0}}
    """

class HistoryTableItem(QTableWidgetItem):
    def __init__(self,value,job_id):
        super().__init__(str(value));self.job_id=job_id;self.sort_value=value;self.setData(Qt.UserRole,job_id);self.setToolTip(str(value))
    def __lt__(self,other):
        left,right=self.sort_value,getattr(other,"sort_value",other.text())
        if isinstance(left,(int,float)) and isinstance(right,(int,float)):return left<right
        return str(left).casefold()<str(right).casefold()

class DraggableChatList(QListWidget):
    def __init__(self):
        super().__init__(); self.setObjectName("chatList"); self.setDragEnabled(True); self.setSelectionMode(QAbstractItemView.ExtendedSelection)
    def startDrag(self, supported):
        ids=[str(i.data(Qt.UserRole)) for i in self.selectedItems()]
        if not ids:return
        mime=QMimeData(); mime.setData("application/x-academic-chat-peer-ids",",".join(ids).encode())
        drag=QDrag(self); drag.setMimeData(mime); drag.exec(Qt.CopyAction)
class CollectionTree(QTreeWidget):
    chatsDropped=Signal(int,list)
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DropOnly); self.setDropIndicatorShown(True); self.setHeaderHidden(True);self.setSelectionMode(QAbstractItemView.ExtendedSelection);self.setSelectionBehavior(QAbstractItemView.SelectRows)
    def dragEnterEvent(self,e): e.acceptProposedAction() if e.mimeData().hasFormat("application/x-academic-chat-peer-ids") else super().dragEnterEvent(e)
    def dragMoveEvent(self,e): e.acceptProposedAction() if e.mimeData().hasFormat("application/x-academic-chat-peer-ids") else super().dragMoveEvent(e)
    def dropEvent(self,e):
        item=self.itemAt(e.position().toPoint())
        if item and item.data(0,TREE_NODE_KIND_ROLE)=="collection" and e.mimeData().hasFormat("application/x-academic-chat-peer-ids"):
            peers=[int(x) for x in bytes(e.mimeData().data("application/x-academic-chat-peer-ids")).decode().split(",") if x]
            self.chatsDropped.emit(int(item.data(0,Qt.UserRole)),peers); e.acceptProposedAction()
        else: super().dropEvent(e)

class FileDropTextEdit(QPlainTextEdit):
    filesDropped=Signal(list)
    sendRequested=Signal()
    def keyPressEvent(self,event):
        if getattr(self,"send_on_enter",False) and event.key() in (Qt.Key_Return,Qt.Key_Enter) and not (event.modifiers()&Qt.ShiftModifier):
            self.sendRequested.emit();event.accept();return
        super().keyPressEvent(event)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
        else:super().dragEnterEvent(event)
    def dropEvent(self,event):
        paths=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:self.filesDropped.emit(paths);event.acceptProposedAction()
        else:super().dropEvent(event)

class MessageBubbleRow(QWidget):
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.outgoing = bool(message.get("outgoing"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        row = QHBoxLayout(self); row.setContentsMargins(10, 3, 10, 3); row.setSpacing(0)
        self.bubble = QFrame(objectName="outgoingBubble" if self.outgoing else "incomingBubble")
        self.bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        content = QVBoxLayout(self.bubble); content.setContentsMargins(12, 8, 12, 8); content.setSpacing(5)
        sender = QLabel("Siz" if self.outgoing else (message.get("sender_name") or "Telegram"), objectName="messageSender")
        body_text = message.get("text") or "[Medya veya dosya]"
        body = QLabel(body_text, objectName="messageText"); body.setWordWrap(True); body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        raw_stamp=(message.get("date") or "").replace("T", " ");stamp=raw_stamp.split(" ")[-1][:5] if len(raw_stamp)>10 else raw_stamp[:5]
        footer = QLabel(stamp, objectName="messageTime"); footer.setAlignment(Qt.AlignRight)
        self.body = body; self.sender = sender; self.footer = footer
        content.addWidget(sender); content.addWidget(body); content.addWidget(footer)
        if self.outgoing: row.addStretch(1); row.addWidget(self.bubble)
        else: row.addWidget(self.bubble); row.addStretch(1)
    def set_bubble_limit(self, width):
        max_content=max(180,width-26);metrics=self.body.fontMetrics()
        longest=max((metrics.horizontalAdvance(line) for line in self.body.text().splitlines()),default=0)
        content_width=min(max_content,max(220,longest+2))
        self.bubble.setMaximumWidth(max_content+26);self.body.setFixedWidth(content_width)
        self.sender.setMaximumWidth(max_content);self.footer.setMaximumWidth(max_content)
        bounds=metrics.boundingRect(QRect(0,0,content_width,10000),Qt.TextWordWrap,self.body.text())
        self.body.setMinimumHeight(max(metrics.height(),bounds.height()+4))
        self.bubble.layout().activate();self.layout().activate();self.adjustSize()

class MessageListWidget(QListWidget):
    def __init__(self):
        super().__init__(); self.setObjectName("messages"); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.setWordWrap(True); self.setSpacing(3)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_bubble_widths)
    def _sync_bubble_widths(self):
        width = max(240, int(self.viewport().width() * .76))
        for index in range(self.count()):
            item = self.item(index); row = self.itemWidget(item)
            if row:
                row.set_bubble_limit(width); item.setSizeHint(QSize(max(1, self.viewport().width()), row.sizeHint().height() + 28))

class ConnectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Telegram hesabını bağla"); self.setMinimumWidth(470); self.service=None; self.user=None; self._authorized=False
        lay=QVBoxLayout(self); lay.addWidget(QLabel("Telegram API bilgileri"))
        info=QLabel("API ID ve API Hash bilgilerinizi my.telegram.org üzerinden alın. Bu uygulama Telegram Bot API kullanmaz; mesajlar kişisel hesabınızdan gönderilir."); info.setWordWrap(True); info.setObjectName("muted"); lay.addWidget(info)
        form=QFormLayout(); self.apiid=QLineEdit(PREFS.value("telegram/api_id","")); self.apihash=QLineEdit(); self.apihash.setEchoMode(QLineEdit.Password); self.apihash.setText(security.get_secret("api_hash") or "")
        self.phone=QLineEdit(); self.phone.setPlaceholderText("+90…"); self.code=QLineEdit(); self.code.setPlaceholderText("Telegram doğrulama kodu"); self.code.hide(); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setPlaceholderText("İki aşamalı doğrulama şifresi"); self.password.hide()
        form.addRow("API ID",self.apiid); form.addRow("API Hash",self.apihash); form.addRow("Telefon",self.phone); form.addRow("Kod",self.code); form.addRow("2FA şifresi",self.password); lay.addLayout(form)
        self.status=QLabel("Oturum dosyası bu Windows kullanıcısının uygulama verileri klasöründe tutulur."); self.status.setWordWrap(True); self.status.setObjectName("muted"); lay.addWidget(self.status)
        row=QHBoxLayout(); self.sendcode=QPushButton("Kod gönder"); self.sendcode.setObjectName("primary"); self.sendcode.clicked.connect(self._request_code); self.login=QPushButton("Doğrula ve bağlan"); self.login.clicked.connect(self._login); self.login.hide(); cancel=QPushButton("Kapat"); cancel.clicked.connect(self.reject); row.addWidget(self.sendcode); row.addWidget(self.login); row.addStretch(); row.addWidget(cancel); lay.addLayout(row)
    def _service(self):
        api_id=int(self.apiid.text().strip()); api_hash=self.apihash.text().strip()
        if not api_hash or api_id<1: raise ValueError("API ID ve API Hash bilgilerini girin")
        self.service=TelegramService(app_data_dir()/"telegram_user_session")
        return api_id,api_hash
    def _request_code(self): asyncio.create_task(self._request_code_async())
    async def _request_code_async(self):
        try:
            api_id,api_hash=self._service(); await self.service.connect(api_id,api_hash)
            if await self.service.client.is_user_authorized():
                self._authorized=True; self.user=await self.service.client.get_me(); self.accept(); return
            await self.service.request_code(self.phone.text().strip()); self.code.show(); self.login.show(); self.sendcode.setEnabled(False); self.status.setText("Kod Telegram uygulamanıza gönderildi. Kodu girin.")
        except Exception as e:self.status.setText(f"Bağlantı kurulamadı: {e}")
    def _login(self):asyncio.create_task(self._login_async())
    async def _login_async(self):
        try:
            result=await self.service.sign_in(self.phone.text().strip(),self.code.text().strip())
            if result.get("needs_password"):
                self.password.show(); self.status.setText("İki aşamalı doğrulama şifresini girin ve yeniden doğrulayın.")
                result=await self.service.sign_in(self.phone.text().strip(),self.code.text().strip(),self.password.text()) if self.password.text() else result
            if result.get("authorized"):
                self._authorized=True; self.user=result["user"]
                try:security.save_secret("api_hash",self.apihash.text().strip())
                except Exception as e:QMessageBox.warning(self,"Güvenli saklama kullanılamıyor",f"Bu oturumda API Hash işletim sistemi kasasına kaydedilemedi. Yeniden açılışta tekrar girmeniz gerekebilir.\n\n{e}")
                PREFS.setValue("telegram/api_id",self.apiid.text().strip()); self.accept()
            elif self.password.text(): self.status.setText("Giriş tamamlanamadı; kodu/şifreyi kontrol edin.")
            else:self.status.setText("Kod kabul edilmedi. Yeniden deneyin.")
        except Exception as e:self.status.setText(f"Doğrulama başarısız: {e}")
    def closeEvent(self,event):
        if self.service and not self._authorized:asyncio.create_task(self.service.disconnect())
        super().closeEvent(event)

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle("Akademik Sohbet Yöneticisi");self.setWindowIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));self.resize(1550,950);self.setMinimumSize(1050,650);self.setStyleSheet(_theme_stylesheet(False,"#A90025"))
        self.store=Store();self.telegram=None;self.bulk=None;self.bulk_task=None;self._allow_close=False;self.dialogs={};self.selected_peer=None;self.reply_to=None;self.current_collection=None;self.active_collection_ids=[];self.active_recipient_ids=[];self.context_mode="none";self._chat_open_generation=0;self.active_nav="chats";self.active_kind="Tümü";self.pending_chat_files=[];self._build();self._load_settings();self.refresh_chats();self.refresh_tree();self.refresh_history();self._update_pending_files()
        api_hash=security.get_secret("api_hash");api_id=PREFS.value("telegram/api_id","")
        if api_hash and api_id:QTimer.singleShot(300,lambda:asyncio.create_task(self._reconnect()))
        elif not PREFS.value("onboarding/dismissed",False,type=bool):QTimer.singleShot(600,self._first_run_connect)
    def _first_run_connect(self):
        if self.isVisible():self.connect_telegram();PREFS.setValue("onboarding/dismissed",True)
    def _build(self):
        root=QWidget(objectName="root");outer=QVBoxLayout(root);outer.setContentsMargins(12,9,12,8);outer.setSpacing(9);outer.addWidget(self._header());body=QHBoxLayout();body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        self.main_splitter=QSplitter(Qt.Horizontal);self.main_splitter.setChildrenCollapsible(False);self.main_splitter.setHandleWidth(7);self.sidebar=self._sidebar();self.main_splitter.addWidget(self.sidebar)
        self.splitter=QSplitter(Qt.Horizontal);self.splitter.setChildrenCollapsible(False);self.splitter.setHandleWidth(7);self.splitter.addWidget(self._center_panel());self.splitter.addWidget(self._conversation_panel());self.splitter.setSizes(self.store.preference("panel_sizes",[460,920]));self.splitter.setStretchFactor(1,1);self.main_splitter.addWidget(self.splitter);self.main_splitter.setSizes(self.store.preference("main_panel_sizes",[210,1340]));self.main_splitter.setStretchFactor(1,1);body.addWidget(self.main_splitter,1);outer.addLayout(body,1);self.setCentralWidget(root);self.setStatusBar(QStatusBar());self.statusBar().showMessage("Telegram bağlantısı kurulmadı")
        self.splitter.splitterMoved.connect(lambda *_:self.store.set_preference("panel_sizes",self.splitter.sizes()))
        self.main_splitter.splitterMoved.connect(lambda *_:self.store.set_preference("main_panel_sizes",self.main_splitter.sizes()))
        self.tray=QSystemTrayIcon(self);self.tray.setIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));self.tray.setToolTip("Akademik Sohbet Yöneticisi");self.tray.show()
    def _header(self):
        f=QFrame(objectName="topbar");f.setFixedHeight(68);h=QHBoxLayout(f);h.setContentsMargins(12,6,12,6);logo=QLabel();pix=QPixmap(str(APP_DIR/"assets"/"rumeli_logo.png"));logo.setPixmap(pix.scaled(130,48,Qt.KeepAspectRatio,Qt.SmoothTransformation));h.addWidget(logo);v=QVBoxLayout();v.addWidget(QLabel("Akademik Sohbet Yöneticisi",objectName="brandTitle"));v.addWidget(QLabel("Telegram sohbet ve klasör yönetimi",objectName="brandSubtitle"));h.addLayout(v);h.addStretch();self.global_search=QLineEdit();self.global_search.setPlaceholderText("Sohbetlerde ara…  Ctrl+K");self.global_search.setFixedWidth(330);self.global_search.textChanged.connect(lambda _:self.refresh_chats());h.addWidget(self.global_search);shortcut=QShortcut(QKeySequence("Ctrl+K"),self);shortcut.activated.connect(self.global_search.setFocus);self.connection_label=QLabel("●  Bağlantı yok");h.addWidget(self.connection_label);self.account_label=QLabel("Telegram kullanıcısı");h.addWidget(self.account_label);return f
    def _sidebar(self):
        f=QFrame(objectName="sidebar");f.setMinimumWidth(150);f.setMaximumWidth(360);v=QVBoxLayout(f);v.setContentsMargins(9,10,9,8)
        self.nav={}
        for text,icon,key in [("Sohbetler","◉","chats"),("Klasörler","▤","folders"),("Toplu Mesajlaşma","➤","bulk"),("Gönderim Geçmişi","◷","history"),("Filtreler","▽","filters"),("Ayarlar","⚙","settings")]:
            b=QPushButton(f"{icon}   {text}");b.setMinimumHeight(39);b.setStyleSheet("text-align:left;padding:8px 7px");b.clicked.connect(lambda _,k=key:self.navigate(k));self.nav[key]=b;v.addWidget(b)
        v.addStretch();self.credit=QLabel("Arş. Gör. Muhammed Yusuf Batur tarafından geliştirilmiştir.");self.credit.setWordWrap(True);self.credit.setStyleSheet("color:#9298a7;padding:5px 4px");v.addWidget(self.credit);self._mark_nav("chats");return f
    def _center_panel(self):
        f=QFrame(objectName="panel");f.setMinimumWidth(300);v=QVBoxLayout(f);v.setContentsMargins(10,9,10,9);self.center_stack=QStackedWidget(objectName="centerStack");v.addWidget(self.center_stack)
        # Chat/collection page
        p=QWidget();pv=QVBoxLayout(p);pv.setContentsMargins(0,0,0,0);self.tabs=QTabWidget();pv.addWidget(self.tabs)
        cp=QWidget();cv=QVBoxLayout(cp);cv.setContentsMargins(3,8,3,2);self.chat_search=QLineEdit();self.chat_search.setPlaceholderText("Sohbetlerde ara…");self.chat_search.textChanged.connect(lambda _:self.refresh_chats());cv.addWidget(self.chat_search)
        chips=QHBoxLayout();self.filters={}
        for label in ["Tümü","Gruplar","Kişiler","Kanallar","Botlar"]:
            b=QPushButton(label);b.setCheckable(True);b.setChecked(label=="Tümü");b.clicked.connect(lambda _,x=label:self.set_filter(x));chips.addWidget(b);self.filters[label]=b
        cv.addLayout(chips);self.chat_list=DraggableChatList();self.chat_list.setIconSize(QSize(40,40));self.chat_list.setWordWrap(True);self.chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.chat_list.setSelectionBehavior(QAbstractItemView.SelectRows);self.chat_list.itemSelectionChanged.connect(self._chat_selected);self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu);self.chat_list.customContextMenuRequested.connect(self._chat_menu);cv.addWidget(self.chat_list,1);self.tabs.addTab(cp,"◉  Sohbetler")
        fp=QWidget();fv=QVBoxLayout(fp);fv.setContentsMargins(3,8,3,2);fh=QHBoxLayout();fh.addWidget(QLabel("Klasörler",objectName="sectionTitle"));fh.addStretch();self.add_collection_btn=QPushButton("＋ Yeni klasör");self.add_collection_btn.clicked.connect(self.create_collection);fh.addWidget(self.add_collection_btn);fv.addLayout(fh);self.collection_search=QLineEdit();self.collection_search.setPlaceholderText("Klasörlerde ara…");self.collection_search.textChanged.connect(lambda _:self.refresh_tree());fv.addWidget(self.collection_search);self.tree=CollectionTree();self.tree.itemClicked.connect(self._collection_selected);self.tree.itemDoubleClicked.connect(self._collection_selected);self.tree.setContextMenuPolicy(Qt.CustomContextMenu);self.tree.customContextMenuRequested.connect(self._collection_menu);self.tree.chatsDropped.connect(self._dropped_chats);fv.addWidget(self.tree,1);self.tabs.addTab(fp,"▤  Klasörler");self.tabs.currentChanged.connect(lambda i:self.navigate("chats" if i==0 else "folders"));self.center_stack.addWidget(p)
        self.settings_page=self._settings_page();self.history_page=self._history_page();self.filters_page=self._filters_page();self.bulk_page=self._bulk_page()
        for page in [self.settings_page,self.history_page,self.filters_page,self.bulk_page]:self.center_stack.addWidget(page)
        return f
    def _conversation_panel(self):
        self.conversation=QFrame(objectName="conversation");self.conversation.setMinimumWidth(360);v=QVBoxLayout(self.conversation);v.setContentsMargins(0,0,0,0);v.setSpacing(0);head=QFrame(objectName="chatHeader");h=QHBoxLayout(head);h.setContentsMargins(15,10,15,10);hv=QVBoxLayout();self.chat_title=QLabel("Sohbet seçin",objectName="sectionTitle");self.chat_meta=QLabel("Telegram mesajları burada yüklenecek",objectName="muted");hv.addWidget(self.chat_title);hv.addWidget(self.chat_meta);h.addLayout(hv);h.addStretch();self.message_search=QLineEdit();self.message_search.setPlaceholderText("Bu sohbette ara");self.message_search.setMaximumWidth(250);self.message_search.returnPressed.connect(self.search_messages);h.addWidget(self.message_search);v.addWidget(head)
        self.older_messages_btn=QPushButton("↑  Önceki mesajları yükle");self.older_messages_btn.setObjectName("olderMessages");self.older_messages_btn.clicked.connect(self.load_older_messages);v.addWidget(self.older_messages_btn,0,Qt.AlignHCenter);self.messages=MessageListWidget();self.messages.itemDoubleClicked.connect(self._message_action);self.messages.setContextMenuPolicy(Qt.CustomContextMenu);self.messages.customContextMenuRequested.connect(self._message_menu);v.addWidget(self.messages,1)
        compose=QFrame(objectName="compose");compose_v=QVBoxLayout(compose);compose_v.setContentsMargins(12,8,12,8);self.pending_files_label=QLabel("");self.pending_files_label.setObjectName("muted");compose_v.addWidget(self.pending_files_label);ch=QHBoxLayout();ch.setSpacing(8);attach=QPushButton("📎");attach.setToolTip("Dosya ekle");attach.clicked.connect(self.attach_to_chat);ch.addWidget(attach);self.message_input=FileDropTextEdit();self.message_input.send_on_enter=False;self.message_input.setMaximumHeight(90);self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin…");self.message_input.filesDropped.connect(self._add_chat_files);self.message_input.sendRequested.connect(lambda:asyncio.create_task(self.send_message()));ch.addWidget(self.message_input,1);self.clear_attachments=QPushButton("Ekleri kaldır");self.clear_attachments.clicked.connect(self._clear_chat_files);ch.addWidget(self.clear_attachments);send=QPushButton("Gönder");send.setObjectName("primary");send.clicked.connect(self.send_message);ch.addWidget(send);compose_v.addLayout(ch);v.addWidget(compose);return self.conversation
    def _history_page(self):
        p=QWidget();v=QVBoxLayout(p);h=QHBoxLayout();h.addWidget(QLabel("Gönderim geçmişi",objectName="sectionTitle"));h.addStretch();self.retry_btn=QPushButton("Başarısızları yeniden dene");self.retry_btn.clicked.connect(self.retry_failed);h.addWidget(self.retry_btn);self.cancel_history_job_btn=QPushButton("Seçili işi iptal et");self.cancel_history_job_btn.clicked.connect(self.cancel_selected_history_job);h.addWidget(self.cancel_history_job_btn);b=QPushButton("Yenile");b.clicked.connect(self.refresh_history);h.addWidget(b);v.addLayout(h)
        self.history=QTableWidget(0,7);self.history.setHorizontalHeaderLabels(["Tarih","Koleksiyon","Durum","Başarılı","Toplam","Mesaj","Ekler"]);header=self.history.horizontalHeader();header.setSectionResizeMode(QHeaderView.Interactive);header.setStretchLastSection(False);header.setMinimumSectionSize(90);self.history.setColumnWidth(0,170);self.history.setColumnWidth(1,260);self.history.setColumnWidth(2,110);self.history.setColumnWidth(3,90);self.history.setColumnWidth(4,90);self.history.setColumnWidth(5,320);self.history.setColumnWidth(6,200);self.history.setSortingEnabled(True);self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded);self.history.setSelectionBehavior(QAbstractItemView.SelectRows);v.addWidget(self.history,1)
        self.target_detail=QListWidget();self.target_detail.setMaximumHeight(200);self.target_detail.setSelectionMode(QAbstractItemView.SingleSelection);v.addWidget(QLabel("Alıcı sonuçları"));v.addWidget(self.target_detail);self.cancel_history_target_btn=QPushButton("Seçili bekleyen alıcıyı iptal et");self.cancel_history_target_btn.clicked.connect(self.cancel_selected_history_target);v.addWidget(self.cancel_history_target_btn);self.history.itemSelectionChanged.connect(self._history_selected);return p
    def _filters_page(self):
        p=QWidget();v=QVBoxLayout(p);v.addWidget(QLabel("Filtreler ve görünürlük",objectName="sectionTitle"));self.visible_mode=QComboBox();self.visible_mode.addItems(["Tüm sohbetler","Yalnızca gruplar","Yalnızca kişiler","Yalnızca koleksiyonlardakiler","Gizlenen sohbetleri yönet"]);self.visible_mode.currentTextChanged.connect(self.refresh_chats);v.addWidget(QLabel("Sohbet görünümü"));v.addWidget(self.visible_mode);self.notification_mode=QComboBox();self.notification_mode.addItems(["Tüm bildirimler","Yalnızca koleksiyonlar","Sessiz mod"]);self.notification_mode.currentTextChanged.connect(lambda x:self.store.set_preference("notifications/mode",x));v.addWidget(QLabel("Uygulama bildirim modu"));v.addWidget(self.notification_mode);self.notification_preview=QCheckBox("Bildirimlerde ileti metnini göster");self.notification_preview.setChecked(True);self.notification_preview.toggled.connect(lambda x:self.store.set_preference("notifications/preview",x));v.addWidget(self.notification_preview);self.visibility_list=QListWidget();self.visibility_list.setSelectionMode(QAbstractItemView.ExtendedSelection);v.addWidget(QLabel("Sohbetler · çoklu seçim yapabilirsiniz"));v.addWidget(self.visibility_list,1);row=QHBoxLayout();hide=QPushButton("Seçilileri gizle");unhide=QPushButton("Gizlemeyi kaldır");hide.clicked.connect(lambda:self._set_hidden_ids([i.data(Qt.UserRole) for i in self.visibility_list.selectedItems()],True));unhide.clicked.connect(lambda:self._unhide_selected());row.addWidget(hide);row.addWidget(unhide);v.addLayout(row);return p
    def _bulk_page(self):
        p=QWidget();v=QVBoxLayout(p);v.addWidget(QLabel("Toplu mesajlaşma",objectName="sectionTitle"));v.addWidget(QLabel("Bir koleksiyon seçip alıcıları inceleyin. Mesajlar yalnızca her bir sohbet için gönderim onayından sonra gönderilir."));self.bulk_collection_combo=QComboBox();self.bulk_collection_combo.currentIndexChanged.connect(self._bulk_collection_changed);v.addWidget(self.bulk_collection_combo);self.bulk_recipients=QListWidget();v.addWidget(self.bulk_recipients,1);b=QPushButton("Mesaj ve dosya gönder…");b.setObjectName("primary");b.clicked.connect(self.start_bulk);v.addWidget(b);self.cancel_job_btn=QPushButton("Bekleyen işleri iptal et");self.cancel_job_btn.clicked.connect(self.cancel_bulk);v.addWidget(self.cancel_job_btn);return p
    def _settings_page(self):
        p=QScrollArea(objectName="settingsPage");p.setWidgetResizable(True);p.setFrameShape(QFrame.NoFrame);inner=QWidget(objectName="settingsInner");v=QVBoxLayout(inner);v.addWidget(QLabel("Ayarlar",objectName="sectionTitle"))
        appearance=QGroupBox("Görünüm");form=QFormLayout(appearance);self.theme=QComboBox();self.theme.addItems(["Açık","Koyu","Sistem ayarı"]);self.theme.currentTextChanged.connect(self.apply_theme);form.addRow("Tema",self.theme);self.font=QComboBox();self.font.addItems(["Segoe UI","Arial","Calibri","Tahoma","Verdana"]);self.font.currentTextChanged.connect(self.apply_font);form.addRow("Yazı tipi",self.font);row=QHBoxLayout();self.font_size=QSlider(Qt.Horizontal);self.font_size.setRange(10,20);self.font_size.valueChanged.connect(self.apply_font);self.font_px=QLabel("13 px");row.addWidget(self.font_size);row.addWidget(self.font_px);form.addRow("Yazı boyutu",row);self.accent_btn=QPushButton("Vurgu rengini seç");self.accent_btn.clicked.connect(self.choose_accent);form.addRow("Vurgu rengi",self.accent_btn);self.density=QComboBox();self.density.addItems(["Rahat","Standart","Yoğun"]);self.density.currentTextChanged.connect(self.apply_density);form.addRow("Liste yoğunluğu",self.density);v.addWidget(appearance)
        background=QGroupBox("Sohbet arka planı");bl=QHBoxLayout(background);self.bg_path=QLineEdit();self.bg_path.setReadOnly(True);self.bg_path.setPlaceholderText("Görsel seçilmedi");pick=QPushButton("Görsel seç…");pick.clicked.connect(self.choose_background);self.bg_color_btn=QPushButton("Düz renk seç…");self.bg_color_btn.clicked.connect(self.choose_background_color);clear=QPushButton("Varsayılana dön");clear.clicked.connect(self.clear_background);bl.addWidget(self.bg_path,1);bl.addWidget(pick);bl.addWidget(self.bg_color_btn);bl.addWidget(clear);v.addWidget(background)
        account=QGroupBox("Telegram hesabı");al=QVBoxLayout(account);self.account_status=QLabel("Bağlı değil");al.addWidget(self.account_status);ar=QHBoxLayout();connect=QPushButton("Hesabı bağla / değiştir");connect.setObjectName("primary");connect.clicked.connect(self.connect_telegram);disconnect=QPushButton("Bağlantıyı kes");disconnect.clicked.connect(lambda:asyncio.create_task(self.disconnect_telegram()));sync=QPushButton("Sohbetleri eşitle");sync.clicked.connect(lambda:asyncio.create_task(self.sync_chats()));logout=QPushButton("Telegram oturumundan çıkış yap");logout.clicked.connect(self.logout_telegram);ar.addWidget(connect);ar.addWidget(disconnect);ar.addWidget(sync);al.addLayout(ar);al.addWidget(logout);secure=QLabel("API Hash, işletim sisteminin kimlik bilgisi kasasında saklanır. Telegram oturumu kullanıcı uygulama verileri klasöründedir.");secure.setWordWrap(True);secure.setObjectName("muted");al.addWidget(secure);v.addWidget(account)
        options=QGroupBox("Görünürlük");ol=QVBoxLayout(options);self.credit_check=QCheckBox("Küçük geliştirici bilgisini göster");self.credit_check.setChecked(True);self.credit_check.toggled.connect(self.credit.setVisible);ol.addWidget(self.credit_check);self.confirm_send=QCheckBox("Toplu gönderim öncesi alıcı onayını zorunlu tut");self.confirm_send.setChecked(True);ol.addWidget(self.confirm_send);v.addWidget(options);v.addStretch();p.setWidget(inner);return p
    def _header_dummy(self):pass
    def _mark_nav(self,key):
        for k,b in self.nav.items():b.setProperty("active",k==key);b.style().unpolish(b);b.style().polish(b)
    def navigate(self,key):
        self.active_nav=key;self._mark_nav(key);self.conversation.show()
        if key in ("chats","folders"):self.center_stack.setCurrentIndex(0);self.tabs.setCurrentIndex(0 if key=="chats" else 1);return
        index={"settings":1,"history":2,"filters":3,"bulk":4}[key];self.center_stack.setCurrentIndex(index)
        if key in ("settings","history","filters","bulk"):self.conversation.hide()
        if key=="history":self.refresh_history()
        if key=="filters":self.refresh_hidden()
        if key=="bulk":self.refresh_bulk_collections()
    def set_filter(self,key):
        self.active_kind=key
        for k,b in self.filters.items():b.setChecked(k==key)
        self.refresh_chats()
    def refresh_chats(self):
        if not hasattr(self,"chat_list"):return
        keep_peer=self.selected_peer;self.chat_list.blockSignals(True)
        query=(self.chat_search.text().strip() or self.global_search.text().strip())
        mode=self.visible_mode.currentText() if hasattr(self,"visible_mode") else "Tüm sohbetler"
        include_hidden=mode=="Gizlenen sohbetleri yönet"
        kind={"Gruplar":"Grup","Kişiler":"Kişi","Kanallar":"Kanal","Botlar":"Bot"}.get(self.active_kind)
        if mode=="Yalnızca gruplar":kind="Grup"
        if mode=="Yalnızca kişiler":kind="Kişi"
        rows=self.store.chats(query.strip(),kind,include_hidden)
        if mode=="Yalnızca koleksiyonlardakiler":
            ids={c['peer_id'] for collection in self.store.collections() for c in self.store.collection_chats(collection['id'],True)};rows=[r for r in rows if r['peer_id'] in ids]
        if mode=="Gizlenen sohbetleri yönet":rows=[r for r in rows if r['hidden']]
        self.chat_list.clear()
        if not rows and not self.store.chats(include_hidden=True):
            item=QListWidgetItem("Telegram hesabı bağlı değil\nAyarlar bölümünden hesabınızı bağlayıp sohbetleri eşitleyin.");item.setFlags(Qt.ItemIsEnabled);self.chat_list.addItem(item);self.chat_list.blockSignals(False);return
        for row in rows:
            title=f"{row['title']}\n{row.get('last_message') or row['kind']} · {row.get('last_message_at') or ''}"
            if row['hidden']:title="◌  "+title
            item=QListWidgetItem(title);item.setData(Qt.UserRole,row['peer_id']);item.setToolTip(row['title']);item.setIcon(self._avatar_icon(row['title']));item.setSizeHint(QSize(0,self._chat_row_height()));self.chat_list.addItem(item)
            if keep_peer is not None and int(row['peer_id'])==int(keep_peer):self.chat_list.setCurrentItem(item,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
        self.chat_list.blockSignals(False)
    def _chat_row_height(self):
        base={"Rahat":76,"Standart":66,"Yoğun":56}.get(self.density.currentText() if hasattr(self,"density") else "Rahat",66)
        return round(base*(self.font_size.value()/13)) if hasattr(self,"font_size") else base
    def _avatar_icon(self,title):
        seed=sum((i+1)*ord(ch) for i,ch in enumerate(title));palette=["#bb3151","#7356b8","#3478a8","#287c6b","#bd7440","#546a9f"];color=QColor(palette[seed%len(palette)]);pix=QPixmap(38,38);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.setBrush(color);p.setPen(Qt.NoPen);p.drawEllipse(1,1,36,36);p.setPen(Qt.white);font=QFont("Segoe UI",11,QFont.Bold);p.setFont(font);p.drawText(pix.rect(),Qt.AlignCenter,"".join(x[0] for x in title.split()[:2]).upper()[:2] or "?");p.end();return QIcon(pix)
    def refresh_tree(self):
        if not hasattr(self,"tree"):return
        selected=[]
        for old in self.tree.selectedItems():
            selected.append((old.data(0,TREE_NODE_KIND_ROLE),old.data(0,Qt.UserRole),old.data(0,TREE_OWNER_COLLECTION_ROLE)))
        if not selected and self.current_collection is not None:selected=[("collection",self.current_collection,None)]
        query=self.collection_search.text().strip().lower();self.tree.clear();self._tree_items={}
        collections=self.store.collections();by_parent={}
        for c in collections:by_parent.setdefault(c['parent_id'],[]).append(c)
        for siblings in by_parent.values():siblings.sort(key=lambda c:(c['sort_order'],c['name'].casefold()))
        memo={}
        def subtree_matches(cid):
            if cid in memo:return memo[cid]
            c=next((x for x in collections if x['id']==cid),None)
            chats=self.store.collection_chats(cid,False) if c else []
            memo[cid]=bool(c and (query in c['name'].casefold() or any(query in r['title'].casefold() for r in chats) or any(subtree_matches(x['id']) for x in by_parent.get(cid,[]))))
            return memo[cid]
        def append_children(parent_id,parent_item=None):
            for c in by_parent.get(parent_id,[]):
                if query and not subtree_matches(c['id']):continue
                item=QTreeWidgetItem([f"{c['icon']}  {c['name']}  ({c['chat_count']})"]);item.setData(0,Qt.UserRole,c['id']);item.setData(0,TREE_NODE_KIND_ROLE,"collection");item.setForeground(0,QColor(c['color']));self._tree_items[c['id']]=item
                if parent_item is None:self.tree.addTopLevelItem(item)
                else:parent_item.addChild(item)
                if ("collection",c['id'],None) in selected:
                    item.setSelected(True)
                    self.tree.setCurrentItem(item,0,QItemSelectionModel.NoUpdate)
                for chat in self.store.collection_chats(c['id'],False):
                    if query and query not in chat['title'].casefold():continue
                    chat_item=QTreeWidgetItem([f"◉  {chat['title']}  ·  {chat['kind']}"]);chat_item.setData(0,Qt.UserRole,chat['peer_id']);chat_item.setData(0,TREE_NODE_KIND_ROLE,"chat");chat_item.setData(0,TREE_OWNER_COLLECTION_ROLE,c['id']);chat_item.setToolTip(0,chat['title']);item.addChild(chat_item)
                    if ("chat",chat['peer_id'],c['id']) in selected:
                        chat_item.setSelected(True)
                        self.tree.setCurrentItem(chat_item,0,QItemSelectionModel.NoUpdate)
                append_children(c['id'],item)
                if query:item.setExpanded(True)
        append_children(None)
        self.refresh_bulk_collections()
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
    def create_collection(self):
        name,ok=QInputDialog.getText(self,"Yeni klasör","Klasör adı:")
        if ok and name:
            parent=self.current_collection if self.active_nav=="folders" and self.context_mode in ("collection","selection") and len(self.active_collection_ids)==1 else None
            try:self.current_collection=self.store.create_collection(name,parent);self.refresh_tree()
            except Exception as e:QMessageBox.warning(self,"Klasör oluşturulamadı",str(e))
    def _collection_selected(self,item,*args):
        if item is None:return
        nodes=self.tree.selectedItems()
        if item not in nodes:nodes=[item]
        collection_ids=[];direct_ids=[];owner_ids=[]
        for node in nodes:
            kind=node.data(0,TREE_NODE_KIND_ROLE)
            if kind=="collection":collection_ids.append(int(node.data(0,Qt.UserRole)))
            elif kind=="chat":
                direct_ids.append(int(node.data(0,Qt.UserRole)))
                if node.data(0,TREE_OWNER_COLLECTION_ROLE) is not None:owner_ids.append(int(node.data(0,TREE_OWNER_COLLECTION_ROLE)))
        collection_ids=list(dict.fromkeys(collection_ids));direct_ids=list(dict.fromkeys(direct_ids))
        if len(nodes)==1 and not collection_ids and len(direct_ids)==1:
            self._activate_chat_context(direct_ids[0],owner_ids[0] if owner_ids else None);return
        target_map={}
        for cid in collection_ids:
            for row in self.store.collection_chats(cid,True):target_map[int(row['peer_id'])]=row
        for peer_id in direct_ids:
            row=self.store.chat(peer_id)
            if row and row['available'] and not row['hidden']:target_map[peer_id]=row
        self._chat_open_generation+=1;self.context_mode="collection" if len(collection_ids)==1 and not direct_ids else "selection"
        self.selected_peer=None;self.active_collection_ids=collection_ids;self.active_recipient_ids=list(target_map)
        self.current_collection=collection_ids[0] if len(collection_ids)==1 else (owner_ids[0] if owner_ids else None)
        self.reply_to=None;self._clear_chat_files();self.older_messages_btn.setEnabled(False);self.message_search.setEnabled(False)
        if len(collection_ids)==1 and not direct_ids:
            c=next((x for x in self.store.collections() if x['id']==collection_ids[0]),None)
            title=c['name'] if c else "Klasör"
            meta=f"{len(target_map)} benzersiz sohbet · klasörün tüm alt dalları · yalnız bu klasöre yapılan gönderimler"
        else:
            labels=[]
            for cid in collection_ids:
                c=next((x for x in self.store.collections() if x['id']==cid),None)
                if c:labels.append(c['name'])
            labels.extend((self.store.chat(pid) or {}).get('title','Sohbet') for pid in direct_ids)
            title=f"{len(labels)} klasör/sohbet seçildi" if labels else "Seçim"
            meta=f"{len(target_map)} benzersiz alıcı · Ctrl ile çoklu seçim"
        self.chat_title.setText(title);self.chat_meta.setText(meta)
        self.message_input.send_on_enter=False;self.message_input.setPlaceholderText("Seçili klasör ve sohbetlere gönderilecek mesaj… (Enter: yeni satır)")
        self.messages.clear();self._render_collection_history()
    def _activate_chat_context(self,peer_id,owner_collection=None):
        row=self.store.chat(peer_id)
        if not row:return
        self._chat_open_generation+=1;generation=self._chat_open_generation
        self.context_mode="chat";self.selected_peer=int(peer_id);self.active_collection_ids=[];self.active_recipient_ids=[int(peer_id)];self.current_collection=owner_collection
        self.reply_to=None;self._clear_chat_files();self.older_messages_btn.setEnabled(True);self.message_search.setEnabled(True)
        self.chat_title.setText(row['title']);self.chat_meta.setText(f"{row['kind']} · {row.get('username') or 'Telegram'}")
        self.message_input.send_on_enter=True;self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin… (Enter: gönder, Shift+Enter: yeni satır)");self.messages.clear()
        asyncio.create_task(self._open_telegram_chat(int(peer_id),generation))
    def _render_collection_history(self):
        self.messages.clear()
        rows=self.store.collection_messages(self.active_collection_ids,100)
        for job in reversed(rows):
            body=job['message'] or ""
            try:
                files=json.loads(job.get('files_json') or '[]')
            except (TypeError,json.JSONDecodeError):files=[]
            if files:body=(body+"\n" if body else "")+"📎 "+", ".join(Path(f).name for f in files)
            if not body:body="[Ekli dosya]"
            body+=f"\n\nTeslim durumu: {job.get('sent') or 0}/{job.get('total') or 0} · {job['status']}"
            entry={"kind":"collection_job","job_id":job['id'],"peer_id":None,"message_id":job['id'],"sender_id":None,"sender_name":"Siz · Klasör gönderimi","text":body,"date":job['created_at'],"outgoing":1,"media_json":job.get('files_json')}
            self._append_message_bubble(entry)
        self.messages.scrollToBottom()
    def _tree_nodes_for_context(self,item):
        if item is None:return []
        if not item.isSelected():
            self.tree.clearSelection();item.setSelected(True);self.tree.setCurrentItem(item,0,QItemSelectionModel.NoUpdate)
        return self.tree.selectedItems()
    def _tree_target_ids(self,nodes):
        collection_ids=[];peer_ids=[]
        for node in nodes:
            kind=node.data(0,TREE_NODE_KIND_ROLE);value=node.data(0,Qt.UserRole)
            if kind=="collection":collection_ids.append(int(value))
            elif kind=="chat":peer_ids.append(int(value))
        return list(dict.fromkeys(collection_ids)),list(dict.fromkeys(peer_ids))
    def _collection_menu(self,pos):
        item=self.tree.itemAt(pos)
        if not item:return
        nodes=self._tree_nodes_for_context(item);kind=item.data(0,TREE_NODE_KIND_ROLE);cid=item.data(0,Qt.UserRole)
        menu=QMenu(self.tree);send=menu.addAction("Seçili klasör/sohbetlere mesaj gönder…")
        new=rename=move_action=up_action=down_action=color_action=icon_action=delete=remove=None
        if kind=="collection":
            menu.addSeparator();new=menu.addAction("Alt klasör oluştur");rename=menu.addAction("Yeniden adlandır");move_action=menu.addAction("Başka klasöre taşı…");up_action=menu.addAction("Sıralamada yukarı al");down_action=menu.addAction("Sıralamada aşağı al");color_action=menu.addAction("Renk seç…");icon_action=menu.addAction("Simge seç…");delete=menu.addAction("Klasörü sil")
        elif kind=="chat":
            menu.addSeparator();remove=menu.addAction("Sohbeti bu klasörden çıkar")
        chosen=menu.exec(self.tree.mapToGlobal(pos))
        if chosen==send:
            collection_ids,peer_ids=self._tree_target_ids(nodes)
            self._collection_selected(item)
            self._start_bulk(collection_ids=collection_ids,direct_peer_ids=peer_ids,preserve_view=True)
        elif chosen==new:
            name,ok=QInputDialog.getText(self,"Alt klasör","Klasör adı:")
            if ok and name:self.store.create_collection(name,int(cid));self.refresh_tree()
        elif chosen==rename:
            old_name=item.text().split("  ",1)[-1].split("  (")[0]
            name,ok=QInputDialog.getText(self,"Klasörü yeniden adlandır","Yeni ad:",text=old_name)
            if ok and name:self.store.rename_collection(int(cid),name);self.refresh_tree()
        elif chosen==delete:
            if QMessageBox.question(self,"Klasörü sil","Klasör ve alt klasörleri silinsin mi? Telegram sohbetleri etkilenmez.") == QMessageBox.Yes:self.store.delete_collection(int(cid));self.current_collection=None;self.refresh_tree()
        elif chosen==remove:
            owner=item.data(0,TREE_OWNER_COLLECTION_ROLE)
            if owner is not None:self.store.remove_chat_from_collection(int(owner),int(cid));self.refresh_tree()
        elif chosen==move_action:
            choices=["(Kök düzey)"];collections=[c for c in self.store.collections() if c['id']!=int(cid)]
            choices.extend(" › ".join(self.store.collection_path(c['id'])) for c in collections)
            label,ok=QInputDialog.getItem(self,"Klasörü taşı","Yeni üst klasör:",choices,0,False)
            if ok:
                parent=None if label==choices[0] else collections[choices.index(label)-1]['id']
                try:self.store.move_collection(int(cid),parent);self.refresh_tree()
                except Exception as e:QMessageBox.warning(self,"Taşıma başarısız",str(e))
        elif chosen==up_action:self.store.reorder_collection(int(cid),-1);self.refresh_tree()
        elif chosen==down_action:self.store.reorder_collection(int(cid),1);self.refresh_tree()
        elif chosen==color_action:
            color=QColorDialog.getColor(QColor('#A90025'),self,"Klasör rengini seç")
            if color.isValid():
                with self.store.db() as db:db.execute("UPDATE collections SET color=? WHERE id=?",(color.name(),int(cid)))
                self.refresh_tree()
        elif chosen==icon_action:
            icon,ok=QInputDialog.getText(self,"Klasör simgesi","Bir emoji veya kısa simge:",text="📁")
            if ok and icon.strip():
                with self.store.db() as db:db.execute("UPDATE collections SET icon=? WHERE id=?",(icon.strip()[:8],int(cid)))
                self.refresh_tree()
    def _dropped_chats(self,cid,peer_ids):
        self.store.add_chats_to_collection(cid,peer_ids);self.refresh_tree();self.statusBar().showMessage(f"{len(peer_ids)} sohbet klasöre eklendi",4000)
    def _chat_menu(self,pos):
        item=self.chat_list.itemAt(pos)
        if not item:return
        peers=self._chat_peers_for_context(item)
        if not peers:return
        menu=QMenu(self.chat_list);hide=menu.addAction("Seçilileri gizle");add=menu.addAction("Seçilileri klasöre ekle");chosen=menu.exec(self.chat_list.mapToGlobal(pos))
        if chosen==hide:self.store.set_hidden(peers,True);self.refresh_chats()
        elif chosen==add:
            cs=self.store.collections();names=[" › ".join(self.store.collection_path(c['id'])) for c in cs]
            if not cs:QMessageBox.information(self,"Klasör yok","Önce Klasörler sekmesinden bir klasör oluşturun.");return
            name,ok=QInputDialog.getItem(self,"Klasöre ekle","Hedef klasör:",names,0,False)
            if ok:self.store.add_chats_to_collection(cs[names.index(name)]['id'],peers);self.refresh_tree();self.statusBar().showMessage(f"{len(peers)} sohbet klasöre eklendi",5000)
    def _chat_peers_for_context(self,item):
        if item.data(Qt.UserRole) is None:return []
        # Right-clicking an unselected row makes it the sole target. Right-clicking
        # an already selected row preserves the current multi-selection.
        if not item.isSelected():
            self.chat_list.clearSelection()
            self.chat_list.setCurrentItem(item,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
        return [int(i.data(Qt.UserRole)) for i in self.chat_list.selectedItems() if i.data(Qt.UserRole) is not None]
    def _chat_selected(self):
        item=self.chat_list.currentItem()
        if not item or item.data(Qt.UserRole) is None:return
        self._activate_chat_context(int(item.data(Qt.UserRole)))
    async def _open_telegram_chat(self,peer_id,generation=None):
        generation=self._chat_open_generation if generation is None else generation
        await self.load_history(peer_id,generation=generation)
        if generation!=self._chat_open_generation or self.context_mode!="chat" or self.selected_peer!=peer_id:return
        if self.telegram:
            rows=self.store.messages(peer_id,1)
            if rows:
                try:await self.telegram.mark_read(peer_id,rows[-1]['message_id']);self.store.clear_unread(peer_id);self.refresh_chats()
                except Exception:self.statusBar().showMessage("Okundu durumu Telegram tarafından onaylanmadı",5000)
    async def load_history(self,peer_id,before=None,generation=None):
        if not self.telegram:return
        generation=self._chat_open_generation if generation is None else generation
        try:
            rows=await self.telegram.history(peer_id,50,before);self.store.cache_messages([{k:r[k] for k in ['peer_id','message_id','sender_id','sender_name','text','date','outgoing','media_json']} for r in rows])
            if generation==self._chat_open_generation and self.context_mode=="chat" and self.selected_peer==peer_id:self._render_messages(peer_id)
        except Exception as e:
            if generation==self._chat_open_generation and self.selected_peer==peer_id:self.statusBar().showMessage(f"Mesaj geçmişi yüklenemedi: {e}",10000)
    def load_older_messages(self):
        if self.selected_peer is None or not self.telegram:return
        peer_id=self.selected_peer;generation=self._chat_open_generation;rows=self.store.messages(peer_id,100)
        if rows:asyncio.create_task(self.load_history(peer_id,rows[0]['message_id'],generation))
    def _render_messages(self,peer_id):
        if self.context_mode!="chat" or self.selected_peer!=peer_id:return
        self.messages.clear()
        for m in self.store.messages(peer_id,100):
            self._append_message_bubble(m)
        self.messages.scrollToBottom()
    def _append_message_bubble(self,message):
        item=QListWidgetItem();item.setData(Qt.UserRole,message);row=MessageBubbleRow(message);row.set_bubble_limit(max(240,int(self.messages.viewport().width()*.76)));self.messages.addItem(item);self.messages.setItemWidget(item,row);item.setSizeHint(QSize(max(1,self.messages.viewport().width()),row.sizeHint().height()+28))
    @asyncSlot()
    async def send_message(self):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():QMessageBox.information(self,"Telegram bağlı değil","Mesaj göndermek için Telegram hesabını bağlayın.");return
        text=self.message_input.toPlainText().strip()
        if not text and not self.pending_chat_files:return
        if self.context_mode in ("collection","selection"):
            self._start_bulk(collection_ids=self.active_collection_ids,direct_peer_ids=self.active_recipient_ids,preserve_view=True,initial_message=text,initial_files=list(self.pending_chat_files));return
        if self.context_mode!="chat" or self.selected_peer is None:QMessageBox.information(self,"Sohbet seçin","Önce bir Telegram sohbeti veya klasör seçin.");return
        peer_id=self.selected_peer;generation=self._chat_open_generation;files=list(self.pending_chat_files)
        try:
            if files:await self.telegram.send_files(peer_id,files,caption=text,progress_callback=self._upload_progress,reply_to=self.reply_to)
            else:await self.telegram.send_text(peer_id,text,reply_to=self.reply_to)
            if generation!=self._chat_open_generation or self.selected_peer!=peer_id:return
            self.message_input.clear();self.pending_chat_files.clear();self.reply_to=None;self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin…");self._update_pending_files();await self.load_history(peer_id,generation=generation)
        except Exception as e:QMessageBox.warning(self,"Mesaj gönderilemedi",str(e))
    def attach_to_chat(self):
        if not self.telegram or self.selected_peer is None:QMessageBox.information(self,"Sohbet seçin","Telegram bağlantısı ve sohbet seçimi gerekli.");return
        paths,_=QFileDialog.getOpenFileNames(self,"Dosya veya medya ekle");self._add_chat_files(paths)
    def _add_chat_files(self,paths):
        for path in paths:
            if Path(path).is_file() and path not in self.pending_chat_files:self.pending_chat_files.append(path)
        self._update_pending_files()
    def _update_pending_files(self):
        if hasattr(self,"pending_files_label"):
            names=[Path(p).name for p in self.pending_chat_files];self.pending_files_label.setText(("Ekler: "+" · ".join(names)) if names else "");self.clear_attachments.setEnabled(bool(names))
    def _clear_chat_files(self):self.pending_chat_files.clear();self._update_pending_files()
    def _upload_progress(self,current,total):
        self.statusBar().showMessage(f"Dosya yükleniyor: {int(100*current/max(total,1))}%")
    def _message_menu(self,pos):
        item=self.messages.itemAt(pos)
        if not item or not item.data(Qt.UserRole):return
        m=item.data(Qt.UserRole)
        if isinstance(m,dict) and m.get("kind")=="collection_job":
            details=self.store.job_targets(m['job_id'])
            lines=[f"{r['peer_title']} · {r['status']}"+(f" · {r['error']}" if r['error'] else "") for r in details]
            QMessageBox.information(self,"Klasör gönderim durumu","\n".join(lines) or "Alıcı kaydı bulunamadı.");return
        if isinstance(m,dict) and m.get("kind")=="collection_member":
            menu=QMenu(self.messages);remove=menu.addAction("Bu klasörden çıkar");chosen=menu.exec(self.messages.mapToGlobal(pos))
            if chosen==remove and self.current_collection:self.store.remove_chat_from_collection(self.current_collection,m['peer_id']);self._collection_selected(self.tree.currentItem());self.refresh_tree()
            return
        menu=QMenu(self.messages);reply=menu.addAction("Yanıtla");copy=menu.addAction("Metni kopyala");download=menu.addAction("Dosyayı indir…") if m.get('media_json') else None;edit=menu.addAction("Mesajı düzenle") if m['outgoing'] else None;delete=menu.addAction("Mesajı sil") if m['outgoing'] else None;chosen=menu.exec(self.messages.mapToGlobal(pos))
        if chosen==reply:self.reply_to=m['message_id'];self.message_input.setPlaceholderText(f"{m['sender_name'] or 'Mesaj'} yanıtlanıyor…");self.message_input.setFocus()
        elif chosen==copy:QApplication.clipboard().setText(m['text'])
        elif chosen==download:asyncio.create_task(self._download_message(m))
        elif chosen==edit:
            text,ok=QInputDialog.getMultiLineText(self,"Mesajı düzenle","Metin:",m['text'])
            if ok:asyncio.create_task(self._edit_message(m,text))
        elif chosen==delete and QMessageBox.question(self,"Mesajı sil","Telegram'dan da silinsin mi?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:asyncio.create_task(self._delete_message(m))
    def _message_action(self,item):self._message_menu(self.messages.visualItemRect(item).center())
    async def _download_message(self,m):
        try:default_name=json.loads(m.get('media_json') or '{}').get('name') or "telegram_file"
        except (TypeError,json.JSONDecodeError):default_name="telegram_file"
        path,_=QFileDialog.getSaveFileName(self,"Dosyayı kaydet",default_name)
        if not path:return
        try:await self.telegram.download_media(m['peer_id'],m['message_id'],path);self.statusBar().showMessage(f"Kaydedildi: {path}",6000)
        except Exception as e:QMessageBox.warning(self,"İndirme başarısız",str(e))
    async def _edit_message(self,m,text):
        try:await self.telegram.edit_message(m['peer_id'],m['message_id'],text);await self.load_history(m['peer_id'])
        except Exception as e:QMessageBox.warning(self,"Düzenleme başarısız",str(e))
    async def _delete_message(self,m):
        try:await self.telegram.delete_message(m['peer_id'],m['message_id']);await self.load_history(m['peer_id'])
        except Exception as e:QMessageBox.warning(self,"Silme başarısız",str(e))
    def search_messages(self):
        if not self.telegram or self.selected_peer is None:return
        asyncio.create_task(self._search_messages())
    async def _search_messages(self):
        query=self.message_search.text().strip()
        if not query:return
        try:
            rows=await self.telegram.search_messages(self.selected_peer,query)
            self.messages.clear()
            for m in reversed(rows):
                file_obj=getattr(m,"file",None);file_name=getattr(file_obj,"name",None)
                self._append_message_bubble({"peer_id":self.selected_peer,"message_id":m.id,"sender_id":getattr(m,"sender_id",None),"sender_name":"Siz" if m.out else str(getattr(m,"sender_id",None) or "Telegram"),"text":m.message or "","date":m.date.isoformat() if m.date else "","outgoing":int(bool(m.out)),"media_json":json.dumps({"name":file_name}) if file_name else None})
        except Exception as e:QMessageBox.warning(self,"Arama başarısız",str(e))
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
            primary=collection_ids[0] if collection_ids else None
            sender=BulkSender(self.store,self.telegram);job=sender.prepare_job(primary,dlg.message.toPlainText(),dlg.files,dlg.selected_targets,collection_ids=collection_ids);self.bulk=sender;self.refresh_history()
            if preserve_view:
                if collection_ids:self._render_collection_history()
                self.message_input.clear();self.pending_chat_files.clear();self.reply_to=None;self._update_pending_files();self.message_input.setPlaceholderText("Seçili klasör ve sohbetlere gönderilecek mesaj…")
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
            values=[j['created_at'],coll,j['status'],j['sent'] or 0,j['total'] or 0,message,attachment_names]
            for col,val in enumerate(values):
                item=HistoryTableItem(val,j['id'])
                if col==6 and files:item.setToolTip("\n".join(files))
                self.history.setItem(row,col,item)
        self.history.setSortingEnabled(True)
        if self.history.rowCount():self.history.selectRow(0)
    def _history_selected(self):
        items=self.history.selectedItems()
        if not items:
            self.target_detail.clear();self.cancel_history_job_btn.setEnabled(False);self.cancel_history_target_btn.setEnabled(False);return
        jobid=items[0].data(Qt.UserRole)
        if not jobid:return
        self.target_detail.clear();targets=self.store.job_targets(jobid);active=any(t['status'] in ('pending','sending') for t in targets);self.cancel_history_job_btn.setEnabled(active)
        for t in targets:
            item=QListWidgetItem(f"{t['peer_title']}  ·  {t['status']}"+(f"  ·  {t['error']}" if t['error'] else ""));item.setData(Qt.UserRole,(jobid,t['peer_id'],t['status']));self.target_detail.addItem(item)
        self.cancel_history_target_btn.setEnabled(any(t['status']=='pending' for t in targets))
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
    def refresh_hidden(self):
        if not hasattr(self,"visibility_list"):return
        self.visibility_list.clear()
        for r in self.store.chats(include_hidden=True):
            i=QListWidgetItem(("◌  " if r['hidden'] else "●  ")+r['title']);i.setData(Qt.UserRole,r['peer_id']);self.visibility_list.addItem(i)
    def _set_hidden_from_chatlist(self,hidden):
        peers=[int(i.data(Qt.UserRole)) for i in self.chat_list.selectedItems()];self.store.set_hidden(peers,hidden);self.refresh_chats();self.refresh_hidden()
    def _set_hidden_ids(self,peers,hidden):
        self.store.set_hidden([int(p) for p in peers if p is not None],hidden);self.refresh_chats();self.refresh_hidden()
    def _unhide_selected(self):
        peers=[int(i.data(Qt.UserRole)) for i in self.visibility_list.selectedItems()];self.store.set_hidden(peers,False);self.refresh_hidden();self.refresh_chats()
    def connect_telegram(self):
        dlg=ConnectDialog(self)
        if dlg.exec()==QDialog.Accepted:
            PREFS.setValue("onboarding/dismissed",True)
            self.telegram=dlg.service
            if self._connected(dlg.user):asyncio.create_task(self.sync_chats())
            else:asyncio.create_task(self._discard_new_account_session())
    async def _reconnect(self):
        try:
            api_id=int(PREFS.value("telegram/api_id"));api_hash=security.get_secret("api_hash");self.telegram=TelegramService(app_data_dir()/"telegram_user_session");result=await self.telegram.connect(api_id,api_hash)
            if result.get('authorized'):
                if self._connected(result['user']):await self.sync_chats()
                else:await self._discard_new_account_session()
            else:
                await self.telegram.disconnect();self.telegram=None;self.connection_label.setText("●  Yeniden giriş gerekli")
        except Exception as e:self.connection_label.setText("●  Bağlantı kurulamadı");self.statusBar().showMessage(f"Telegram bağlantı hatası: {e}",10000)
    def _connected(self,user):
        user_id=getattr(user,'id',None);old_id=self.store.preference('telegram/user_id')
        if old_id is not None and user_id is not None and int(old_id)!=int(user_id):
            answer=QMessageBox.question(self,"Farklı Telegram hesabı", "Başka bir Telegram hesabına geçiyorsunuz. Önceki hesaba ait sohbet önbelleği temizlenecek; koleksiyon klasörleri korunacak fakat sohbet üyelikleri silinecek. Devam edilsin mi?",QMessageBox.Yes|QMessageBox.No)
            if answer!=QMessageBox.Yes:return False
            self.store.clear_telegram_data()
        if user_id is not None:self.store.set_preference('telegram/user_id',int(user_id))
        name=" ".join(filter(None,[getattr(user,'first_name',None),getattr(user,'last_name',None)])) or getattr(user,'username',None) or "Telegram hesabı";self.account_label.setText(name);self.connection_label.setText("●  Telegram bağlı");self.connection_label.setStyleSheet("color:#18833b;font-weight:600");self.account_status.setText(f"Bağlı hesap: {name}");self.statusBar().showMessage("Telegram hesabı bağlandı")
        if self.telegram:self.telegram.start_updates(self._on_live_message)
        return True
    async def _discard_new_account_session(self):
        if self.telegram:
            try:await self.telegram.log_out()
            except Exception:await self.telegram.disconnect()
        self.telegram=None;self.connection_label.setText("●  Bağlantı yok");self.account_status.setText("Bağlı değil")
    def _on_live_message(self,row):
        self.store.cache_messages([{k:row[k] for k in ['peer_id','message_id','sender_id','sender_name','text','date','outgoing','media_json']}])
        if not self.store.chat(row['peer_id']):
            self.store.upsert_chats([{"peer_id":row['peer_id'],"access_hash":None,"title":row.get('chat_title') or "Telegram sohbet","kind":"Grup" if row['peer_id']<0 else "Kişi","username":None,"can_send":1,"unread_count":0,"last_message":row['text'] or "Medya","last_message_at":row['date']}])
        else:self.store.update_last_message(row['peer_id'],row['text'] or "Medya",row['date'],incoming=not row['outgoing'])
        self.refresh_chats()
        if self.selected_peer==row['peer_id']:self._render_messages(row['peer_id'])
        if not row['outgoing']:self._show_local_notification(row)
    def _show_local_notification(self,row):
        mode=self.notification_mode.currentText() if hasattr(self,"notification_mode") else self.store.preference('notifications/mode','Tüm bildirimler')
        if mode=="Sessiz mod" or (mode=="Yalnızca koleksiyonlar" and not self.store.is_in_any_collection(row['peer_id'])):return
        chat=self.store.chat(row['peer_id']);title=(chat or {}).get('title',row.get('chat_title') or 'Telegram sohbet');text=(row['text'] or "Yeni bir medya iletisi") if self.notification_preview.isChecked() else "Yeni Telegram iletisi"
        self.tray.showMessage(title,text[:180],QSystemTrayIcon.MessageIcon.Information,5000)
    async def sync_chats(self):
        try:
            rows=await self.telegram.load_dialogs();self.store.upsert_chats(rows,complete_sync=True);self.dialogs={r['peer_id']:r for r in rows};self.refresh_chats();self.refresh_tree();self.statusBar().showMessage(f"{len(rows)} sohbet eşitlendi",6000)
        except Exception as e:QMessageBox.warning(self,"Senkronizasyon başarısız",str(e))
    async def disconnect_telegram(self):
        if self.telegram:await self.telegram.disconnect();self.telegram=None
        self.connection_label.setText("●  Bağlantı yok");self.account_status.setText("Bağlı değil");self.statusBar().showMessage("Telegram bağlantısı kesildi")
    def logout_telegram(self):
        if QMessageBox.question(self,"Telegram oturumundan çıkış yap","Bu bilgisayardaki Telegram kullanıcı oturumu kapatılacak. Yerel klasörler ve gönderim kayıtları korunur. Devam edilsin mi?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:asyncio.create_task(self._discard_new_account_session())
    def _load_settings(self):
        self.theme.setCurrentText(self.store.preference('appearance/theme','Açık'));self.font.setCurrentText(self.store.preference('appearance/font','Segoe UI'));self.font_size.setValue(self.store.preference('appearance/font_size',13));self.density.setCurrentText(self.store.preference('appearance/density','Rahat'));self.notification_mode.setCurrentText(self.store.preference('notifications/mode','Tüm bildirimler'));self.notification_preview.setChecked(self.store.preference('notifications/preview',True));self.credit_check.setChecked(self.store.preference('appearance/credit',True));self.credit.setVisible(self.credit_check.isChecked());self.bg_path.setText(self.store.preference('appearance/background',''));self.accent_btn.setText(self.store.preference('appearance/accent','#a90025'));self.apply_theme();self.apply_font();self.apply_density();self._set_message_background(self.bg_path.text())
    def apply_theme(self,*args):
        if not hasattr(self,'theme'):return
        theme=self.theme.currentText();accent=self.store.preference('appearance/accent','#a90025')
        is_dark=theme=='Koyu' or (theme=='Sistem ayarı' and QApplication.palette().color(QPalette.Window).lightness()<128)
        self.setStyleSheet(_theme_stylesheet(is_dark,accent));self.store.set_preference('appearance/theme',theme)
        if hasattr(self,'messages'):self._set_message_background(self.bg_path.text() if hasattr(self,'bg_path') else '')
    def apply_font(self,*args):
        if not hasattr(self,'font_size'):return
        size=self.font_size.value();family=self.font.currentText();self.font_px.setText(f"{size} pt");f=QFont(family);f.setPointSize(size);QApplication.instance().setFont(f);self.setFont(f)
        for widget in self.findChildren(QWidget):
            widget.setFont(f);widget.updateGeometry();widget.update()
        if hasattr(self,'credit'):
            small=QFont(f);small.setPointSize(max(7,size-4));self.credit.setFont(small)
        if hasattr(self,'chat_list'):
            for i in range(self.chat_list.count()):self.chat_list.item(i).setSizeHint(QSize(0,self._chat_row_height()))
        if hasattr(self,'tree'):self.tree.doItemsLayout()
        self.store.set_preference('appearance/font',family);self.store.set_preference('appearance/font_size',size)
        if self.selected_peer is not None:self._render_messages(self.selected_peer)
    def apply_density(self,*args):
        if not hasattr(self,'chat_list'):return
        spacing={'Rahat':7,'Standart':4,'Yoğun':1}.get(self.density.currentText(),4);self.chat_list.setSpacing(spacing)
        for i in range(self.chat_list.count()):self.chat_list.item(i).setSizeHint(QSize(0,self._chat_row_height()))
        self.store.set_preference('appearance/density',self.density.currentText())
    def choose_accent(self):
        c=QColorDialog.getColor(QColor(self.store.preference('appearance/accent','#a90025')),self)
        if c.isValid():self.store.set_preference('appearance/accent',c.name());self.accent_btn.setText(c.name());self.apply_theme()
    def choose_background(self):
        path,_=QFileDialog.getOpenFileName(self,"Sohbet arka planı seç","","Görseller (*.png *.jpg *.jpeg *.webp)")
        if path:self.bg_path.setText(path);self.store.set_preference('appearance/background',path);self._set_message_background(path)
    def choose_background_color(self):
        color=QColorDialog.getColor(QColor(self.store.preference('appearance/background_color','#f8f8fb')),self,"Sohbet arka plan rengini seç")
        if color.isValid():self.bg_path.clear();self.store.set_preference('appearance/background','');self.store.set_preference('appearance/background_color',color.name());self._set_message_background('')
    def clear_background(self):
        self.bg_path.clear();self.store.set_preference('appearance/background','')
        dark=self.theme.currentText()=='Koyu' or (self.theme.currentText()=='Sistem ayarı' and QApplication.palette().color(QPalette.Window).lightness()<128)
        self.store.set_preference('appearance/background_color','#171c25' if dark else '#eef1f6');self._set_message_background('')
    def _set_message_background(self,path):
        color=self.store.preference('appearance/background_color','#eef1f6' if self.theme.currentText()!='Koyu' else '#171c25') if hasattr(self,'theme') else '#eef1f6'
        if path and Path(path).is_file():
            image_url=Path(path).resolve().as_uri()
            self.messages.setStyleSheet(f"QListWidget#messages{{background-color:{color};background-image:url(\"{image_url}\");background-position:center;background-repeat:no-repeat}}")
        else:self.messages.setStyleSheet(f"QListWidget#messages{{background:{color}}}")
    def closeEvent(self,event):
        if self._allow_close:return super().closeEvent(event)
        if self.bulk and self.bulk.current_job:
            answer=QMessageBox.question(self,"Gönderim sürüyor","Uygulamayı kapatıp bekleyen alıcıları iptal etmek istiyor musunuz? Gönderilmiş mesajlar geri alınamaz.",QMessageBox.Yes|QMessageBox.No)
            if answer!=QMessageBox.Yes:event.ignore();return
            self.bulk.cancel()
        if self.telegram:
            event.ignore();asyncio.create_task(self._shutdown());return
        self.store.set_preference('appearance/credit',self.credit_check.isChecked());super().closeEvent(event)
    async def _shutdown(self):
        if self.bulk_task and not self.bulk_task.done():
            try:await self.bulk_task
            except Exception:pass
        if self.telegram:
            try:await self.telegram.disconnect()
            except Exception:pass
            self.telegram=None
        self.store.set_preference('appearance/credit',self.credit_check.isChecked());self._allow_close=True;self.close()

def main():
    if sys.platform=="win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IstanbulRumeli.AkademikSohbetYoneticisi")
        except Exception:pass
    app=QApplication(sys.argv);app.setApplicationName("Akademik Sohbet Yöneticisi");app.setApplicationDisplayName("Akademik Sohbet Yöneticisi");app.setWindowIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));app.setFont(QFont('Segoe UI',10));loop=QEventLoop(app);asyncio.set_event_loop(loop);window=MainWindow();window.setWindowIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));window.show()
    with loop:loop.run_forever()
if __name__=='__main__':main()
