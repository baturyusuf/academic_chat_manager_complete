"""Notification preferences, inbox and presentation."""
from __future__ import annotations
from PySide6.QtCore import QSignalBlocker, QTime, QTimer, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QTabWidget, QTimeEdit, QVBoxLayout, QWidget

if __package__:
    from .notification_delivery import DesktopNotificationThrottle
    from .ui_common import MENTION_KINDS, NOTIFICATION_KINDS, NOTIFICATION_RULES, NOTIFICATION_SCOPES, _icon_button
else:  # Direct and frozen entry points
    from notification_delivery import DesktopNotificationThrottle
    from ui_common import MENTION_KINDS, NOTIFICATION_KINDS, NOTIFICATION_RULES, NOTIFICATION_SCOPES, _icon_button


class NotificationView:
    """Notification preferences, inbox and presentation."""

    def _init_notification_view(self, clock):
        self._notification_throttle = DesktopNotificationThrottle(clock)

    def _build_notification_banner(self):
        self.notification_banner = QFrame(objectName="notificationBanner")
        row = QHBoxLayout(self.notification_banner)
        row.setContentsMargins(12, 2, 4, 2)
        self.notification_banner_text = QLabel()
        self.notification_banner_text.setTextFormat(Qt.PlainText)
        self.notification_banner_text.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(self.notification_banner_text, 1)
        view = QPushButton("Bildirimi oku")
        view.clicked.connect(self._open_recent_notifications)
        row.addWidget(view)
        close = _icon_button("close", tooltip="Bildirimi kapat")
        close.clicked.connect(self.notification_banner.hide)
        row.addWidget(close)
        self.notification_banner_timer = QTimer(self)
        self.notification_banner_timer.setSingleShot(True)
        self.notification_banner_timer.timeout.connect(self.notification_banner.hide)
        self.notification_banner.hide()
        return self.notification_banner

    def _notifications_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Bildirimler", objectName="sectionTitle"))

        def note(text, parent_layout):
            label = QLabel(text, objectName="muted")
            label.setWordWrap(True)
            parent_layout.addWidget(label)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        general = QScrollArea()
        general.setWidgetResizable(True)
        general.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        general.setWidget(body)
        options = QVBoxLayout(body)
        tabs.addTab(general, "Genel")
        scope_box = QGroupBox("Masaüstü bildirimleri")
        scope_form = QFormLayout(scope_box)
        scope_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.notification_mode = QComboBox()
        self.notification_mode.addItems(NOTIFICATION_SCOPES)
        self.notification_mode.setCurrentText(self.store.preference("notifications/mode", NOTIFICATION_SCOPES[0]))
        self.notification_mode.currentTextChanged.connect(
            lambda value: self.store.set_preference("notifications/mode", value))
        scope_form.addRow("Kapsam", self.notification_mode)
        self.notification_preview = QCheckBox("Bildirimlerde mesaj metnini göster")
        self.notification_preview.setChecked(self.store.preference("notifications/preview", True))
        self.notification_preview.toggled.connect(
            lambda value: self.store.set_preference("notifications/preview", value))
        scope_form.addRow(self.notification_preview)
        note("Bildirimler pencere görünürken uygulama içinde, pencere gizliyken veya "
             "küçültülmüşken Windows’ta gösterilir.", scope_form)
        note("Mesaj metni burada kapatılırsa tüm sohbet türlerinde gizlenir.", scope_form)
        options.addWidget(scope_box)

        kinds_box = QGroupBox("Sohbet türüne göre varsayılanlar")
        kinds_form = QFormLayout(kinds_box)
        kinds_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.notification_kind_modes = {}
        self.notification_kind_previews = {}
        for kind, label in NOTIFICATION_KINDS.items():
            rule_key = f"notifications/kind/{kind}"
            preview_key = f"notifications/preview/{kind}"
            choices = ("all", "mentions", "off") if kind in MENTION_KINDS else ("all", "off")
            combo = self._notification_rule_combo(choices)
            combo.setCurrentIndex(max(0, combo.findData(self.store.preference(rule_key, "all"))))
            combo.currentIndexChanged.connect(
                lambda _, widget=combo, key=rule_key: self.store.set_preference(key, widget.currentData()))
            self.notification_kind_modes[kind] = combo
            preview = QCheckBox("Mesaj metnini göster")
            preview.setAccessibleName(f"{label} · Mesaj metnini göster")
            preview.setChecked(self.store.preference(preview_key, True))
            preview.toggled.connect(
                lambda value, key=preview_key: self.store.set_preference(key, value))
            self.notification_kind_previews[kind] = preview
            row = QVBoxLayout()
            row.addWidget(combo)
            row.addWidget(preview)
            kinds_form.addRow(label, row)
            combo.setAccessibleName(f"{label} · Bildirim kuralı")
        options.addWidget(kinds_box)

        quiet_box = QGroupBox("Sessiz saatler")
        quiet_form = QFormLayout(quiet_box)
        self.notification_quiet = QCheckBox("Sessiz saatleri etkinleştir")
        self.notification_quiet.setChecked(self.store.preference("notifications/quiet", False))
        self.notification_quiet.toggled.connect(
            lambda value: self.store.set_preference("notifications/quiet", value))
        quiet_form.addRow(self.notification_quiet)
        times = []
        for key, label, default in (("start", "Başlangıç", "22:00"), ("end", "Bitiş", "08:00")):
            pref_key = f"notifications/quiet/{key}"
            edit = QTimeEdit()
            edit.setDisplayFormat("HH:mm")
            edit.setTime(QTime.fromString(self.store.preference(pref_key, default), "HH:mm"))
            edit.setEnabled(self.notification_quiet.isChecked())
            self.notification_quiet.toggled.connect(edit.setEnabled)
            edit.timeChanged.connect(
                lambda value, name=pref_key: self.store.set_preference(name, value.toString("HH:mm")))
            quiet_form.addRow(label, edit)
            times.append(edit)
        self.notification_quiet_start, self.notification_quiet_end = times
        self.notification_quiet_priority = QCheckBox("Önemli sohbetlere izin ver")
        self.notification_quiet_priority.setChecked(
            self.store.preference("notifications/quiet/priority", False))
        self.notification_quiet_priority.setEnabled(self.notification_quiet.isChecked())
        self.notification_quiet.toggled.connect(self.notification_quiet_priority.setEnabled)
        self.notification_quiet_priority.toggled.connect(
            lambda value: self.store.set_preference("notifications/quiet/priority", value))
        quiet_form.addRow(self.notification_quiet_priority)
        note("Bilgisayarın yerel saati kullanılır. Başlangıç ve bitiş aynıysa tüm gün sessize alınır.", quiet_form)
        options.addWidget(quiet_box)
        options.addStretch()

        chats = QWidget()
        chats_layout = QVBoxLayout(chats)
        tabs.addTab(chats, "Sohbete özel")
        note("Sohbete özel kurallar tür ayarının önüne geçer. Önemli sohbetler etiketlenir "
             "ve normal bildirimlerin bekleme süresinden etkilenmez. Genel kapsam her zaman uygulanır.", chats_layout)
        self.notification_chat_search = QLineEdit()
        self.notification_chat_search.setPlaceholderText("Sohbet adına göre ara…")
        self.notification_chat_search.setClearButtonEnabled(True)
        self.notification_chat_search.textChanged.connect(self._refresh_notification_chats)
        self.notification_chat_filter = QComboBox()
        self.notification_chat_filter.addItem("Tüm sohbetler", "")
        self.notification_chat_filter.addItem("Önemli sohbetler", "priority")
        for kind, label in NOTIFICATION_KINDS.items():
            self.notification_chat_filter.addItem(label, kind)
        self.notification_chat_filter.currentIndexChanged.connect(self._refresh_notification_chats)
        filters = QHBoxLayout()
        filters.addWidget(self.notification_chat_search, 1)
        filters.addWidget(self.notification_chat_filter)
        chats_layout.addLayout(filters)
        self.notification_chats = QListWidget()
        chats_layout.addWidget(self.notification_chats, 1)
        self.notification_chat_empty = QLabel("Bu filtreye uyan sohbet yok.", objectName="muted")
        chats_layout.addWidget(self.notification_chat_empty)
        self.notification_chat_rule = self._notification_rule_combo(
            ("default", "all", "mentions", "priority", "off"))
        rule_form = QFormLayout()
        rule_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        rule_form.addRow("Seçili sohbetin kuralı", self.notification_chat_rule)
        chats_layout.addLayout(rule_form)
        self.notification_chat_rule.setEnabled(False)
        self.notification_chat_rule.currentIndexChanged.connect(self._change_notification_chat_rule)
        self.notification_chats.currentItemChanged.connect(self._load_notification_chat_rule)

        recent = QWidget()
        recent_layout = QVBoxLayout(recent)
        note("Bu oturumun bildirimleri. Tam metni okumak için bir bildirim seç.", recent_layout)
        self.notification_inbox = QListWidget()
        recent_layout.addWidget(self.notification_inbox, 1)
        self.notification_detail = QPlainTextEdit()
        self.notification_detail.setReadOnly(True)
        self.notification_detail.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.notification_detail.setAccessibleName("Bildirimin tam metni")
        self.notification_detail.setPlaceholderText("Henüz bildirim yok.")
        recent_layout.addWidget(self.notification_detail, 2)
        self.notification_inbox.currentItemChanged.connect(self._read_notification)
        tabs.addTab(recent, "Son bildirimler")
        self.notification_recent_page = recent
        self.notification_tabs = tabs
        return page

    def _open_recent_notifications(self):
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self.navigate("notifications")
        self.notification_tabs.setCurrentWidget(self.notification_recent_page)
        self.notification_inbox.setCurrentRow(0)
        self.notification_banner.hide()

    def _read_notification(self, item, _previous):
        self.notification_detail.setPlainText(item.data(Qt.UserRole) if item else "")

    def _record_notification(self, title, body, show_banner):
        item = QListWidgetItem(f"{QTime.currentTime().toString('HH:mm')} · {title}")
        item.setData(Qt.UserRole, f"{title}\n\n{body}")
        self.notification_inbox.insertItem(0, item)
        if self.notification_inbox.count() > 100:
            self.notification_inbox.takeItem(100)
        if self.notification_inbox.currentItem() is None:
            self.notification_inbox.setCurrentItem(item)
        if show_banner:
            summary = " ".join(body.split())
            summary = summary[:117] + "…" if len(summary) > 120 else summary
            self.notification_banner_text.setText(f"{title} · {summary}")
            self.notification_banner.show()
            self.notification_banner_timer.start(8000)

    @staticmethod
    def _notification_rule_combo(choices):
        combo = QComboBox()
        for choice in choices:
            combo.addItem(NOTIFICATION_RULES[choice], choice)
        return combo

    def _notification_chat_key(self):
        account = self.store.preference("telegram/user_id")
        return f"notifications/chats/{account}" if account is not None else "notifications/chats/local"

    def _refresh_notification_chats(self, *_):
        current = self.notification_chats.currentItem()
        selected = current.data(Qt.UserRole) if current else None
        rules = self.store.preference(self._notification_chat_key(), {})
        query = self.notification_chat_search.text().strip().casefold()
        selected_filter = self.notification_chat_filter.currentData()
        self.notification_chats.clear()
        selected_index = 0
        rows = sorted(self.store.chats(include_hidden=True), key=lambda row: row["title"].casefold())
        for chat in rows:
            if query not in chat["title"].casefold():
                continue
            rule = rules.get(str(chat["peer_id"]), "default")
            if selected_filter == "priority" and rule != "priority":
                continue
            if selected_filter in NOTIFICATION_KINDS and selected_filter != chat["kind"]:
                continue
            suffix = f" · {NOTIFICATION_RULES[rule]}" if rule != "default" else ""
            item = QListWidgetItem(f"{chat['title']} · {chat['kind']}{suffix}")
            item.setData(Qt.UserRole, chat["peer_id"])
            item.setData(Qt.UserRole + 1, chat["kind"])
            item.setData(Qt.UserRole + 2, rule)
            if chat["peer_id"] == selected:
                selected_index = self.notification_chats.count()
            self.notification_chats.addItem(item)
        has_chats = self.notification_chats.count() > 0
        self.notification_chats.setCurrentRow(selected_index if has_chats else -1)
        self.notification_chat_empty.setVisible(not has_chats)

    def _load_notification_chat_rule(self, item, _previous):
        combo = self.notification_chat_rule
        with QSignalBlocker(combo):
            combo.setEnabled(item is not None)
            combo.model().item(combo.findData("mentions")).setEnabled(
                bool(item and item.data(Qt.UserRole + 1) in MENTION_KINDS))
            combo.setCurrentIndex(combo.findData(item.data(Qt.UserRole + 2) if item else "default"))

    def _change_notification_chat_rule(self, _index):
        item = self.notification_chats.currentItem()
        if item:
            peer = str(item.data(Qt.UserRole))
            rule = self.notification_chat_rule.currentData()
            key = self._notification_chat_key()
            rules = self.store.preference(key, {})
            if rule == "default":
                rules.pop(peer, None)
            else:
                rules[peer] = rule
            self.store.set_preference(key, rules)
            self._refresh_notification_chats()

    def _open_chat_notification_settings(self, peer_id):
        self.navigate("notifications")
        self.notification_tabs.setCurrentIndex(1)
        self.notification_chat_search.clear()
        self.notification_chat_filter.setCurrentIndex(0)
        for index in range(self.notification_chats.count()):
            if self.notification_chats.item(index).data(Qt.UserRole) == peer_id:
                self.notification_chats.setCurrentRow(index)
                break

    def _show_local_notification(self, row):
        if row.get("outgoing"):
            return
        peer_id = row["peer_id"]
        window_visible = self._notification_window_is_visible()
        if (window_visible and self.active_nav in ("chats", "folders")
                and self.context_mode == "chat" and self.selected_peer == peer_id
                and self.isActiveWindow()):
            return
        scope = self.notification_mode.currentText()
        if scope == "Sessiz mod":
            return
        if scope == "Yalnızca koleksiyonlar" and not self.store.is_in_any_collection(peer_id):
            return

        chat = self.store.chat(peer_id) or {}
        kind = row.get("chat_kind") or chat.get("kind") or ("Grup" if peer_id < 0 else "Kişi")
        rules = self.store.preference(self._notification_chat_key(), {})
        rule = rules.get(str(peer_id), "default")
        if rule == "default":
            combo = self.notification_kind_modes.get(kind)
            rule = combo.currentData() if combo else "all"
        priority = rule == "priority"
        if scope == "Yalnızca önemli sohbetler" and not priority:
            return
        if rule == "off" or (rule == "mentions" and not row.get("mentioned")):
            return
        if self.notification_quiet.isChecked() and self._in_notification_quiet_hours(QTime.currentTime()):
            if not (priority and self.notification_quiet_priority.isChecked()):
                return

        preview = self.notification_kind_previews.get(kind)
        show_text = self.notification_preview.isChecked() and (preview is None or preview.isChecked())
        title = chat.get("title") or row.get("chat_title") or "Telegram sohbeti"
        body = (row.get("text") or "Yeni bir medya iletisi") if show_text else "Yeni Telegram iletisi"
        if priority:
            title = f"Önemli · {title}"
        self._record_notification(title, body, show_banner=window_visible)
        if window_visible:
            return

        suppressed = self._notification_throttle.record(priority=priority)
        if suppressed is None:
            return
        if suppressed:
            body = f"{suppressed + 1} yeni mesaj · {body}"
        self.tray.showMessage(title, body[:180], QSystemTrayIcon.MessageIcon.Information, 5000)

    def _in_notification_quiet_hours(self, now):
        start = self.notification_quiet_start.time()
        end = self.notification_quiet_end.time()
        if start < end:
            return start <= now < end
        return now >= start or now < end

    def _notification_window_is_visible(self):
        # Qt/Windows can briefly report an on-screen window as inactive while
        # focus moves between child widgets. A native tray toast is queued by
        # Windows and cannot be withdrawn afterward, so visibility is the safe
        # boundary: only notify when the main window is hidden or minimized.
        return self.isVisible() and not self.isMinimized()
