"""Desktop application entry point and main window composition."""
from __future__ import annotations
import asyncio
import certifi
import os
import sys
import uuid
from pathlib import Path
from PySide6.QtCore import QItemSelectionModel, QSettings, QSize, QTime, QTimer, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSplitter, QStackedWidget, QStatusBar, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget
from qasync import QEventLoop
from time import monotonic

# The frozen build must configure CA certificates before Telegram imports
# its HTTP client, which creates an SSL context at import time.
if os.name == "nt" or not os.environ.get("SSL_CERT_FILE") or not Path(os.environ["SSL_CERT_FILE"]).is_file():
    os.environ["SSL_CERT_FILE"] = certifi.where()

if __package__:
    from . import security
    from .appearance_view import AppearanceView
    from .bulk_view import BulkView
    from .chat_view import ChatView
    from .collection_view import CollectionView
    from .media_view import MediaView
    from .notification_view import NotificationView
    from .storage import Store, app_data_dir
    from .telegram_service import TelegramService
    from .ui_common import APP_DIR, COLLECTION_ICON_OPTIONS, TREE_ICON_ROLE, TREE_NODE_KIND_ROLE, TREE_OWNER_COLLECTION_ROLE, _format_local_datetime, _icon_button, _local_datetime, _theme_stylesheet
    from .ui_dialogs import BulkConfirmDialog, BulkPreviewDialog, FullScreenImageDialog, InviteLinksDialog
    from .ui_widgets import ClickableImagePreview, CollectionTree, DraggableChatList, HistoryTableItem, MessageBubbleRow, MessageListWidget
    from .update_view import UpdateView
    from .version import APP_VERSION
else:  # Direct and frozen entry points
    import security
    from appearance_view import AppearanceView
    from bulk_view import BulkView
    from chat_view import ChatView
    from collection_view import CollectionView
    from media_view import MediaView
    from notification_view import NotificationView
    from storage import Store, app_data_dir
    from telegram_service import TelegramService
    from ui_common import APP_DIR, COLLECTION_ICON_OPTIONS, TREE_ICON_ROLE, TREE_NODE_KIND_ROLE, TREE_OWNER_COLLECTION_ROLE, _format_local_datetime, _icon_button, _local_datetime, _theme_stylesheet
    from ui_dialogs import BulkConfirmDialog, BulkPreviewDialog, FullScreenImageDialog, InviteLinksDialog
    from ui_widgets import ClickableImagePreview, CollectionTree, DraggableChatList, HistoryTableItem, MessageBubbleRow, MessageListWidget
    from update_view import UpdateView
    from version import APP_VERSION


PREFS = QSettings("RumeliAcademic", "AcademicChatManager")


class FileDropTextEdit(QPlainTextEdit):
    filesDropped=Signal(list)
    sendRequested=Signal()
    def keyPressEvent(self,event):
        if event.matches(QKeySequence.Paste):
            clipboard=QApplication.clipboard();mime=clipboard.mimeData()
            if mime.hasImage():
                image=clipboard.image()
                if not image.isNull():
                    folder=app_data_dir()/"clipboard_images";folder.mkdir(parents=True,exist_ok=True)
                    image_path=folder/f"pasted_{uuid.uuid4().hex}.png"
                    if image.save(str(image_path),"PNG"):
                        self.filesDropped.emit([str(image_path)]);event.accept();return
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


class ConnectDialog(QDialog):
    def __init__(self,parent=None, *, preferences=None):
        super().__init__(parent); self.setWindowTitle("Telegram hesabını bağla"); self.setMinimumWidth(470); self.service=None; self.user=None; self._authorized=False
        self._preferences = preferences if preferences is not None else PREFS
        lay=QVBoxLayout(self); lay.addWidget(QLabel("Telegram API bilgileri"))
        info=QLabel("API ID ve API Hash bilgilerinizi my.telegram.org üzerinden alın. Bu uygulama Telegram Bot API kullanmaz; mesajlar kişisel hesabınızdan gönderilir."); info.setWordWrap(True); info.setObjectName("muted"); lay.addWidget(info)
        form=QFormLayout(); self.apiid=QLineEdit(self._preferences.value("telegram/api_id","")); self.apihash=QLineEdit(); self.apihash.setEchoMode(QLineEdit.Password); self.apihash.setText(security.get_secret("api_hash") or "")
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
                self._preferences.setValue("telegram/api_id",self.apiid.text().strip()); self.accept()
            elif self.password.text(): self.status.setText("Giriş tamamlanamadı; kodu/şifreyi kontrol edin.")
            else:self.status.setText("Kod kabul edilmedi. Yeniden deneyin.")
        except Exception as e:self.status.setText(f"Doğrulama başarısız: {e}")
    def closeEvent(self,event):
        if self.service and not self._authorized:asyncio.create_task(self.service.disconnect())
        super().closeEvent(event)


class MainWindow(QMainWindow, ChatView, MediaView, CollectionView, BulkView,
                 NotificationView, AppearanceView, UpdateView):
    """Compose the Qt feature views and own the application lifecycle."""

    def _new_menu(self, parent):
        return QMenu(parent)

    def _new_invite_links_dialog(self, entries):
        return InviteLinksDialog(entries, self)

    def _app_data_dir(self):
        return app_data_dir()

    def _notification_clock(self):
        return monotonic()

    def __init__(self, store=None, *, preferences=None):
        super().__init__()
        self.setWindowTitle("Akademik Sohbet Yöneticisi")
        self.setWindowIcon(QIcon(str(APP_DIR / "assets" / "app.ico")))
        self.resize(1550, 950)
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(_theme_stylesheet(False, "#A90025"))
        self._preferences = preferences if preferences is not None else PREFS
        self.store = store if store is not None else Store()
        self.telegram = None
        self.dialogs = {}
        self._allow_close = False
        self.active_nav = "chats"
        self._init_chat_view()
        self._init_media_view()
        self._init_bulk_view()
        self._init_notification_view(self._notification_clock)
        self._init_update_view()
        self._build()
        self._load_settings()
        self.refresh_chats()
        self.refresh_tree()
        self.refresh_history()
        self._update_pending_files()
        api_hash=security.get_secret("api_hash");api_id=self._preferences.value("telegram/api_id","")
        if api_hash and api_id:QTimer.singleShot(300,lambda:asyncio.create_task(self._reconnect()))
        elif not self._preferences.value("onboarding/dismissed",False,type=bool):QTimer.singleShot(600,self._first_run_connect)
        if self._updates_enabled():
            self._update_timer = QTimer(self)
            self._update_timer.setInterval(60 * 60 * 1000)
            self._update_timer.timeout.connect(lambda: asyncio.create_task(self._check_updates()))
            self._update_timer.start()
            QTimer.singleShot(2000, lambda: asyncio.create_task(self._check_updates()))

    def _first_run_connect(self):
        if self.isVisible():self.connect_telegram();self._preferences.setValue("onboarding/dismissed",True)

    def _build(self):
        root=QWidget(objectName="root");outer=QVBoxLayout(root);outer.setContentsMargins(12,9,12,8);outer.setSpacing(5);body=QHBoxLayout();body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        self.main_splitter=QSplitter(Qt.Horizontal);self.main_splitter.setChildrenCollapsible(False);self.main_splitter.setHandleWidth(7);self.sidebar=self._sidebar();self.main_splitter.addWidget(self.sidebar)
        self.splitter=QSplitter(Qt.Horizontal);self.splitter.setChildrenCollapsible(False);self.splitter.setHandleWidth(7);self.splitter.addWidget(self._center_panel());self.splitter.addWidget(self._conversation_panel());self.splitter.setSizes(self.store.preference("panel_sizes",[460,920]));self.splitter.setStretchFactor(1,1);self.main_splitter.addWidget(self.splitter);self.main_splitter.setSizes(self.store.preference("main_panel_sizes",[210,1340]));self.main_splitter.setStretchFactor(1,1);body.addWidget(self.main_splitter,1);outer.addLayout(body,1);self.setCentralWidget(root);self.setStatusBar(QStatusBar());self.statusBar().showMessage("Telegram bağlantısı kurulmadı")
        toolbar=QHBoxLayout();self.sidebar_toggle=_icon_button("panel",tooltip="Menü panelini aç veya kapat");self.sidebar_toggle.clicked.connect(self.toggle_sidebar);toolbar.addWidget(self.sidebar_toggle)
        self.global_search=QLineEdit();self.global_search.setPlaceholderText("Sohbetlerde ara…  Ctrl+K");self.global_search.setFixedWidth(330);self.global_search.textChanged.connect(lambda _:self.refresh_chats());toolbar.addWidget(self.global_search);shortcut=QShortcut(QKeySequence("Ctrl+K"),self);shortcut.activated.connect(self.global_search.setFocus);toolbar.addStretch();self.update_button=QPushButton("Güncelleme mevcut");self.update_button.hide();self.update_button.clicked.connect(self._offer_update);toolbar.addWidget(self.update_button);toolbar.addWidget(QLabel("v"+APP_VERSION));self.connection_label=QLabel("●  Bağlantı yok");toolbar.addWidget(self.connection_label);self.account_label=QLabel("Telegram kullanıcısı");toolbar.addWidget(self.account_label);outer.insertLayout(0,toolbar)
        outer.insertWidget(1, self._build_notification_banner())
        self.splitter.splitterMoved.connect(lambda *_:self.store.set_preference("panel_sizes",self.splitter.sizes()))
        self.main_splitter.splitterMoved.connect(lambda *_:self.store.set_preference("main_panel_sizes",self.main_splitter.sizes()))
        self.tray=QSystemTrayIcon(self);self.tray.setIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));self.tray.setToolTip("Akademik Sohbet Yöneticisi");self.tray.show()
        self.tray.messageClicked.connect(self._open_recent_notifications)
        if not self.store.preference("appearance/sidebar_visible",True):self.sidebar.hide()

    def toggle_sidebar(self):
        if self.sidebar.isVisible():
            self.sidebar.hide();self.store.set_preference("appearance/sidebar_visible",False)
        else:
            self.sidebar.show();self.store.set_preference("appearance/sidebar_visible",True)

    def _sidebar(self):
        f=QFrame(objectName="sidebar");f.setMinimumWidth(150);f.setMaximumWidth(360);v=QVBoxLayout(f);v.setContentsMargins(9,10,9,8)
        brand=QHBoxLayout();logo=QLabel();pix=QPixmap(str(APP_DIR/"assets"/"app.ico"));logo.setPixmap(pix.scaled(30,30,Qt.KeepAspectRatio,Qt.SmoothTransformation));brand.addWidget(logo);brand.addWidget(QLabel("Akademik Sohbet Yöneticisi",objectName="brandTitle"),1);v.addLayout(brand)
        self.nav={}
        for text,key in [("Sohbetler","chats"),("Klasörler","folders"),("Toplu Mesajlaşma","bulk"),("Gönderim Geçmişi","history"),("Filtreler","filters"),("Bildirimler","notifications"),("Ayarlar","settings")]:
            b=_icon_button(key,text);b.setMinimumHeight(39);b.setStyleSheet("text-align:left;padding:8px 7px");b.clicked.connect(lambda _,k=key:self.navigate(k));self.nav[key]=b;v.addWidget(b)
        v.addStretch();self.credit=QLabel("RUDIC tarafından geliştirilmiştir.");self.credit.setWordWrap(True);self.credit.setStyleSheet("color:#9298a7;padding:5px 4px");v.addWidget(self.credit);self._mark_nav("chats");return f

    def _center_panel(self):
        f=QFrame(objectName="panel");f.setMinimumWidth(300);v=QVBoxLayout(f);v.setContentsMargins(10,9,10,9);self.center_stack=QStackedWidget(objectName="centerStack");v.addWidget(self.center_stack)
        # Chat/collection page
        p=QWidget();pv=QVBoxLayout(p);pv.setContentsMargins(0,0,0,0);self.tabs=QTabWidget();pv.addWidget(self.tabs)
        cp=QWidget();cv=QVBoxLayout(cp);cv.setContentsMargins(3,8,3,2);self.chat_search=QLineEdit();self.chat_search.setPlaceholderText("Sohbetlerde ara…");self.chat_search.textChanged.connect(lambda _:self.refresh_chats());cv.addWidget(self.chat_search)
        chips=QHBoxLayout();self.filters={}
        for label in ["Tümü","Gruplar","Kişiler","Kanallar","Botlar"]:
            b=QPushButton(label);b.setCheckable(True);b.setChecked(label=="Tümü");b.clicked.connect(lambda _,x=label:self.set_filter(x));chips.addWidget(b);self.filters[label]=b
        cv.addLayout(chips);self.chat_list=DraggableChatList();self.chat_list.setIconSize(QSize(40,40));self.chat_list.setWordWrap(True);self.chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.chat_list.setSelectionBehavior(QAbstractItemView.SelectRows);self.chat_list.itemSelectionChanged.connect(self._chat_selected);self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu);self.chat_list.customContextMenuRequested.connect(self._chat_menu);self.chat_list.verticalScrollBar().valueChanged.connect(lambda *_:self._queue_visible_avatars());cv.addWidget(self.chat_list,1);self.tabs.addTab(cp,"Sohbetler")
        fp=QWidget();fv=QVBoxLayout(fp);fv.setContentsMargins(3,8,3,2);fh=QHBoxLayout();fh.addWidget(QLabel("Klasörler",objectName="sectionTitle"));fh.addStretch();self.add_collection_btn=_icon_button("plus","Yeni klasör");self.add_collection_btn.clicked.connect(self.create_collection);fh.addWidget(self.add_collection_btn);fv.addLayout(fh);self.collection_search=QLineEdit();self.collection_search.setPlaceholderText("Klasörlerde ara…");self.collection_search.textChanged.connect(lambda _:self.refresh_tree());fv.addWidget(self.collection_search);self.tree=CollectionTree();self.tree.itemClicked.connect(self._collection_selected);self.tree.itemDoubleClicked.connect(self._collection_selected);self.tree.setContextMenuPolicy(Qt.CustomContextMenu);self.tree.customContextMenuRequested.connect(self._collection_menu);self.tree.chatsDropped.connect(self._dropped_chats);fv.addWidget(self.tree,1);self.tabs.addTab(fp,"Klasörler");self.tabs.currentChanged.connect(lambda i:self.navigate("chats" if i==0 else "folders"));self.center_stack.addWidget(p)
        self.settings_page=self._settings_page();self.history_page=self._history_page();self.filters_page=self._filters_page();self.bulk_page=self._bulk_page();self.notifications_page=self._notifications_page()
        for page in [self.settings_page,self.history_page,self.filters_page,self.bulk_page,self.notifications_page]:self.center_stack.addWidget(page)
        return f

    def _conversation_panel(self):
        self.conversation=QFrame(objectName="conversation");self.conversation.setMinimumWidth(360);v=QVBoxLayout(self.conversation);v.setContentsMargins(0,0,0,0);v.setSpacing(0);head=QFrame(objectName="chatHeader");h=QHBoxLayout(head);h.setContentsMargins(15,10,15,10);self.chat_avatar=QLabel();self.chat_avatar.setFixedSize(42,42);h.addWidget(self.chat_avatar);hv=QVBoxLayout();self.chat_title=QLabel("Sohbet seçin",objectName="sectionTitle");self.chat_meta=QLabel("Telegram mesajları burada yüklenecek",objectName="muted");hv.addWidget(self.chat_title);hv.addWidget(self.chat_meta);h.addLayout(hv);h.addStretch();self.message_search=QLineEdit();self.message_search.setPlaceholderText("Bu sohbette ara");self.message_search.setMaximumWidth(250);self.message_search.returnPressed.connect(self.search_messages);h.addWidget(self.message_search);v.addWidget(head)
        self.older_messages_btn=_icon_button("up","Önceki mesajları yükle");self.older_messages_btn.setObjectName("olderMessages");self.older_messages_btn.clicked.connect(self.load_older_messages);v.addWidget(self.older_messages_btn,0,Qt.AlignHCenter);self.messages=MessageListWidget();self.messages.setContextMenuPolicy(Qt.CustomContextMenu);self.messages.customContextMenuRequested.connect(self._message_menu);self.messages.verticalScrollBar().valueChanged.connect(lambda *_:self._schedule_visible_previews());v.addWidget(self.messages,1)
        compose=QFrame(objectName="compose");compose_v=QVBoxLayout(compose);compose_v.setContentsMargins(12,8,12,8)
        self.reply_preview_frame=QFrame(objectName="replyPreviewFrame");reply_row=QHBoxLayout(self.reply_preview_frame);reply_row.setContentsMargins(10,5,6,5);self.reply_preview=QLabel("");self.reply_preview.setWordWrap(True);reply_row.addWidget(self.reply_preview,1);self.clear_reply_btn=_icon_button("close",tooltip="Yanıtı iptal et");self.clear_reply_btn.clicked.connect(self._clear_reply);reply_row.addWidget(self.clear_reply_btn);self.reply_preview_frame.hide();compose_v.addWidget(self.reply_preview_frame)
        self.pending_files_label=QLabel("");self.pending_files_label.setObjectName("muted");compose_v.addWidget(self.pending_files_label);ch=QHBoxLayout();ch.setSpacing(8);attach=_icon_button("attach",tooltip="Dosya ekle");attach.setMinimumSize(38,38);attach.clicked.connect(self.attach_to_chat);ch.addWidget(attach);self.message_input=FileDropTextEdit();self.message_input.send_on_enter=False;self.message_input.setMinimumHeight(42);self.message_input.setMaximumHeight(90);self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin…");self.message_input.filesDropped.connect(self._add_chat_files);self.message_input.sendRequested.connect(self.send_message);ch.addWidget(self.message_input,1);self.emoji_button=_icon_button("emoji",tooltip="Emoji ekle");self.emoji_button.setMinimumSize(38,38);self.emoji_button.clicked.connect(self._show_emoji_picker);ch.addWidget(self.emoji_button);send=_icon_button("bulk","Gönder");send.setObjectName("primary");send.setMinimumHeight(38);send.clicked.connect(self.send_message);ch.addWidget(send);compose_v.addLayout(ch);self.clear_attachments=_icon_button("close","Ekleri kaldır");self.clear_attachments.setObjectName("clearAttachments");self.clear_attachments.setToolTip("Gönderilecek tüm ekleri kaldır");self.clear_attachments.setAccessibleName("Tüm ekleri kaldır");self.clear_attachments.setAccessibleDescription("Mesaj metnini değiştirmeden bekleyen ekleri kaldırır.");self.clear_attachments.clicked.connect(self._clear_chat_files);self.clear_attachments.setVisible(False);clear_row=QHBoxLayout();clear_row.addStretch();clear_row.addWidget(self.clear_attachments);compose_v.addLayout(clear_row);v.addWidget(compose);return self.conversation

    def _filters_page(self):
        p=QWidget();v=QVBoxLayout(p);v.addWidget(QLabel("Filtreler ve görünürlük",objectName="sectionTitle"));self.visible_mode=QComboBox();self.visible_mode.addItems(["Tüm sohbetler","Yalnızca gruplar","Yalnızca kişiler","Yalnızca koleksiyonlardakiler","Gizlenen sohbetleri yönet"]);self.visible_mode.currentTextChanged.connect(self.refresh_chats);v.addWidget(QLabel("Sohbet görünümü"));v.addWidget(self.visible_mode);self.visibility_list=QListWidget();self.visibility_list.setSelectionMode(QAbstractItemView.ExtendedSelection);v.addWidget(QLabel("Sohbetler · çoklu seçim yapabilirsiniz"));v.addWidget(self.visibility_list,1);row=QHBoxLayout();hide=_icon_button("eye-off","Seçilileri gizle");unhide=_icon_button("eye","Gizlemeyi kaldır");hide.clicked.connect(lambda:self._set_hidden_ids([i.data(Qt.UserRole) for i in self.visibility_list.selectedItems()],True));unhide.clicked.connect(lambda:self._unhide_selected());row.addWidget(hide);row.addWidget(unhide);v.addLayout(row);return p

    def _settings_page(self):
        p=QScrollArea(objectName="settingsPage");p.setWidgetResizable(True);p.setFrameShape(QFrame.NoFrame);inner=QWidget(objectName="settingsInner");v=QVBoxLayout(inner);v.addWidget(QLabel("Ayarlar",objectName="sectionTitle"))
        appearance=QGroupBox("Görünüm");form=QFormLayout(appearance);self.theme=QComboBox();self.theme.addItems(["Açık","Koyu","Sistem ayarı"]);self.theme.currentTextChanged.connect(self.apply_theme);form.addRow("Tema",self.theme);self.font=QComboBox();self.font.addItems(["Segoe UI","Arial","Calibri","Tahoma","Verdana"]);self.font.currentTextChanged.connect(self.apply_font);form.addRow("Yazı tipi",self.font);row=QHBoxLayout();self.font_size=QSlider(Qt.Horizontal);self.font_size.setRange(10,20);self.font_size.valueChanged.connect(self.apply_font);self.font_px=QLabel("13 px");row.addWidget(self.font_size);row.addWidget(self.font_px);form.addRow("Yazı boyutu",row);self.accent_btn=QPushButton("Vurgu rengini seç");self.accent_btn.clicked.connect(self.choose_accent);form.addRow("Vurgu rengi",self.accent_btn);self.density=QComboBox();self.density.addItems(["Rahat","Standart","Yoğun"]);self.density.currentTextChanged.connect(self.apply_density);form.addRow("Liste yoğunluğu",self.density);v.addWidget(appearance)
        background=QGroupBox("Sohbet arka planı");bl=QHBoxLayout(background);self.bg_path=QLineEdit();self.bg_path.setReadOnly(True);self.bg_path.setPlaceholderText("Görsel seçilmedi");pick=_icon_button("image","Görsel seç…");pick.clicked.connect(self.choose_background);self.bg_color_btn=QPushButton("Düz renk seç…");self.bg_color_btn.clicked.connect(self.choose_background_color);clear=QPushButton("Varsayılana dön");clear.clicked.connect(self.clear_background);bl.addWidget(self.bg_path,1);bl.addWidget(pick);bl.addWidget(self.bg_color_btn);bl.addWidget(clear);v.addWidget(background)
        account=QGroupBox("Telegram hesabı");al=QVBoxLayout(account);self.account_status=QLabel("Bağlı değil");al.addWidget(self.account_status);ar=QHBoxLayout();connect=QPushButton("Hesabı bağla / değiştir");connect.setObjectName("primary");connect.clicked.connect(self.connect_telegram);disconnect=QPushButton("Bağlantıyı kes");disconnect.clicked.connect(lambda:asyncio.create_task(self.disconnect_telegram()));sync=_icon_button("refresh","Sohbetleri eşitle");sync.clicked.connect(lambda:asyncio.create_task(self.sync_chats()));logout=QPushButton("Telegram oturumundan çıkış yap");logout.clicked.connect(self.logout_telegram);ar.addWidget(connect);ar.addWidget(disconnect);ar.addWidget(sync);al.addLayout(ar);al.addWidget(logout);secure=QLabel("API Hash, işletim sisteminin kimlik bilgisi kasasında saklanır. Telegram oturumu kullanıcı uygulama verileri klasöründedir.");secure.setWordWrap(True);secure.setObjectName("muted");al.addWidget(secure);v.addWidget(account)
        options=QGroupBox("Görünürlük");ol=QVBoxLayout(options);self.credit_check=QCheckBox("Küçük geliştirici bilgisini göster");self.credit_check.setChecked(True);self.credit_check.toggled.connect(self.credit.setVisible);ol.addWidget(self.credit_check);self.confirm_send=QCheckBox("Toplu gönderim öncesi alıcı onayını zorunlu tut");self.confirm_send.setChecked(True);ol.addWidget(self.confirm_send);v.addWidget(options);v.addStretch();p.setWidget(inner);return p

    def _mark_nav(self,key):
        for k,b in self.nav.items():b.setProperty("active",k==key);b.style().unpolish(b);b.style().polish(b)
        self._refresh_ui_icons()

    def navigate(self,key):
        self.active_nav=key;self._mark_nav(key);self.conversation.show()
        if key in ("chats","folders"):self.center_stack.setCurrentIndex(0);self.tabs.setCurrentIndex(0 if key=="chats" else 1);return
        index={"settings":1,"history":2,"filters":3,"bulk":4,"notifications":5}[key];self.center_stack.setCurrentIndex(index)
        self.conversation.hide()
        if key=="history":self.refresh_history()
        if key=="filters":self.refresh_hidden()
        if key=="bulk":self.refresh_bulk_collections()
        if key=="notifications":self._refresh_notification_chats()

    def connect_telegram(self):
        dlg=ConnectDialog(self, preferences=self._preferences)
        if dlg.exec()==QDialog.Accepted:
            self._preferences.setValue("onboarding/dismissed",True)
            asyncio.create_task(self._activate_telegram_service(dlg.service,dlg.user))

    async def _activate_telegram_service(self,service,user):
        previous=self.telegram
        # Invalidate callbacks from the old client before awaiting its shutdown.
        self.telegram=service
        if previous and previous is not service:
            try:await previous.disconnect()
            except Exception:pass
        if self._connected(user):await self.sync_chats()
        else:await self._discard_new_account_session()

    async def _reconnect(self):
        try:
            previous=self.telegram
            self.telegram=None
            if previous:
                try:await previous.disconnect()
                except Exception:pass
            api_id=int(self._preferences.value("telegram/api_id"));api_hash=security.get_secret("api_hash");self.telegram=TelegramService(app_data_dir()/"telegram_user_session");result=await self.telegram.connect(api_id,api_hash)
            if result.get('authorized'):
                if self._connected(result['user']):await self.sync_chats()
                else:await self._discard_new_account_session()
            else:
                await self.telegram.disconnect();self.telegram=None;self.connection_label.setText("●  Yeniden giriş gerekli")
        except Exception as e:self.connection_label.setText("●  Bağlantı kurulamadı");self.statusBar().showMessage(f"Telegram bağlantı hatası: {e}",10000)

    def _connected(self,user):
        self._cancel_image_preview_tasks();self._image_preview_cache.clear()
        user_id=getattr(user,'id',None);old_id=self.store.preference('telegram/user_id')
        if old_id is not None and user_id is not None and int(old_id)!=int(user_id):
            answer=QMessageBox.question(self,"Farklı Telegram hesabı", "Başka bir Telegram hesabına geçiyorsunuz. Önceki hesaba ait sohbet önbelleği temizlenecek; koleksiyon klasörleri korunacak fakat sohbet üyelikleri silinecek. Devam edilsin mi?",QMessageBox.Yes|QMessageBox.No)
            if answer!=QMessageBox.Yes:return False
            self.store.clear_telegram_data()
            self.notification_inbox.clear()
            self.notification_banner.hide()
            self._avatar_cache.clear()
            self._image_preview_cache.clear()
        if user_id is not None:self.store.set_preference('telegram/user_id',int(user_id))
        name=" ".join(filter(None,[getattr(user,'first_name',None),getattr(user,'last_name',None)])) or getattr(user,'username',None) or "Telegram hesabı";self.account_label.setText(name);self.connection_label.setText("●  Telegram bağlı");self.connection_label.setStyleSheet("color:#18833b;font-weight:600");self.account_status.setText(f"Bağlı hesap: {name}");self.statusBar().showMessage("Telegram hesabı bağlandı")
        if self.telegram:
            service=self.telegram
            service.start_updates(
                lambda row,s=service:self._on_live_message(row) if self.telegram is s else None,
                lambda row,s=service:self._on_message_edited(row) if self.telegram is s else None,
                lambda peer_id,max_id,s=service:self._on_message_read(peer_id,max_id) if self.telegram is s else None)
        self._schedule_visible_previews()
        return True

    async def _discard_new_account_session(self):
        service=self.telegram;self.telegram=None
        if service:
            try:await service.log_out()
            except Exception:await service.disconnect()
        self.connection_label.setText("●  Bağlantı yok");self.account_status.setText("Bağlı değil")

    async def sync_chats(self):
        try:
            rows=await self.telegram.load_dialogs();self.store.upsert_chats(rows,complete_sync=True);self.dialogs={r['peer_id']:r for r in rows};self.refresh_chats();self.refresh_tree();self.statusBar().showMessage(f"{len(rows)} sohbet eşitlendi",6000)
            if self.active_nav=="notifications":self._refresh_notification_chats()
        except Exception as e:QMessageBox.warning(self,"Senkronizasyon başarısız",str(e))

    async def disconnect_telegram(self):
        service=self.telegram;self.telegram=None
        if service:await service.disconnect()
        self.connection_label.setText("●  Bağlantı yok");self.account_status.setText("Bağlı değil");self.statusBar().showMessage("Telegram bağlantısı kesildi")

    def logout_telegram(self):
        if QMessageBox.question(self,"Telegram oturumundan çıkış yap","Bu bilgisayardaki Telegram kullanıcı oturumu kapatılacak. Yerel klasörler ve gönderim kayıtları korunur. Devam edilsin mi?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:asyncio.create_task(self._discard_new_account_session())

    def closeEvent(self,event):
        if self._allow_close:self._cancel_image_preview_tasks();return super().closeEvent(event)
        if self.bulk and self.bulk.current_job:
            answer=QMessageBox.question(self,"Gönderim sürüyor","Uygulamayı kapatıp bekleyen alıcıları iptal etmek istiyor musunuz? Gönderilmiş mesajlar geri alınamaz.",QMessageBox.Yes|QMessageBox.No)
            if answer!=QMessageBox.Yes:event.ignore();return
            self.bulk.cancel()
        if self._fullscreen_preview is not None:
            self._fullscreen_preview.reject()
        if self.telegram:
            event.ignore();asyncio.create_task(self._shutdown());return
        self._cancel_image_preview_tasks();self.store.set_preference('appearance/credit',self.credit_check.isChecked());super().closeEvent(event)

    async def _shutdown(self):
        self._cancel_image_preview_tasks()
        if self.bulk_task and not self.bulk_task.done():
            try:await self.bulk_task
            except Exception:pass
        if self.telegram:
            try:await self.telegram.disconnect()
            except Exception:pass
            self.telegram=None
        self.store.set_preference('appearance/credit',self.credit_check.isChecked());self._allow_close=True;self.close()


def main():
    # Offline package smoke test: verify frozen startup imports and version
    # without opening Telegram, the user database or credential storage.
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        return 0 if APP_VERSION == sys.argv[2] and (APP_DIR / "assets" / "app.ico").is_file() else 1
    mutex = None
    if sys.platform=="win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            mutex = kernel.CreateMutexW(None, False, "Local\\AcademicChatManagerRunning")
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IstanbulRumeli.AkademikSohbetYoneticisi")
        except Exception:pass
    app=QApplication(sys.argv);app.setApplicationName("Akademik Sohbet Yöneticisi");app.setApplicationVersion(APP_VERSION);app.setApplicationDisplayName("Akademik Sohbet Yöneticisi");app.setWindowIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));app.setFont(QFont('Segoe UI',10));loop=QEventLoop(app);asyncio.set_event_loop(loop);window=MainWindow();window.setWindowIcon(QIcon(str(APP_DIR/"assets"/"app.ico")));window.show()
    with loop:loop.run_forever()

if __name__=='__main__':sys.exit(main())
