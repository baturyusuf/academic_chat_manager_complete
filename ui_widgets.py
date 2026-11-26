"""Reusable Qt widgets for chats, folders and message rows."""
from __future__ import annotations
import json
from PySide6.QtCore import QEvent, QMimeData, QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QSizePolicy, QTableWidgetItem, QTreeWidget, QVBoxLayout, QWidget

if __package__:
    from .media import decode_media, format_size, safe_filename
    from .ui_common import TREE_NODE_KIND_ROLE, _format_local_datetime
else:  # Direct and frozen entry points
    from media import decode_media, format_size, safe_filename
    from ui_common import TREE_NODE_KIND_ROLE, _format_local_datetime


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


class ClickableImagePreview(QLabel):
    clicked=Signal()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:self.clicked.emit();event.accept();return
        super().mouseReleaseEvent(event)


class MessageBubbleRow(QWidget):
    contextMenuRequested = Signal(QPoint)
    downloadRequested = Signal(dict)

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.message = message
        self.outgoing = bool(message.get("outgoing"))
        self.is_group=message.get("chat_kind") in ("Grup","Kanal")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        row = QHBoxLayout(self); row.setContentsMargins(8, 2, 8, 2); row.setSpacing(5)
        self.bubble = QFrame(self, objectName="outgoingBubble" if self.outgoing else "incomingBubble")
        self.bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        content = QVBoxLayout(self.bubble); content.setContentsMargins(10, 6, 10, 5); content.setSpacing(3)
        # Showing a parentless QLabel creates a top-level window. Parent the
        # labels before setting visibility, even when the row itself is hidden.
        sender = QLabel(message.get("sender_name") or "Telegram", self.bubble, objectName="messageSender")
        sender.setVisible(self.is_group and not self.outgoing)
        attachments=message.get("attachments")
        if attachments is None:
            metadata=decode_media(message.get("media_json"))
            attachments=[{**metadata,"peer_id":message.get("peer_id"),"message_id":message.get("message_id")}] if metadata else []
        body_text = message.get("text") or ("" if attachments else "[Medya veya dosya]")
        body = QLabel(body_text, self.bubble, objectName="messageText"); body.setWordWrap(True); body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        stamp=_format_local_datetime(message.get("date"),"%H:%M")
        edited=message.get("edit_date") and not message.get("edit_hidden")
        footer = QLabel(("düzenlendi · " if edited else "")+stamp, self.bubble, objectName="messageTime"); footer.setAlignment(Qt.AlignRight)
        ticks=QLabel("✓✓" if message.get("read") else "✓",self.bubble,objectName="messageTicks");ticks.setVisible(self.outgoing)
        if edited:
            footer.setToolTip("Düzenlenme zamanı: "+_format_local_datetime(message["edit_date"],"%d.%m.%Y %H:%M:%S"))
        self.body = body; self.sender = sender; self.footer = footer;self.ticks=ticks
        if not self.outgoing and (self.is_group or message.get("chat_kind") in ("Kişi","Bot")):
            avatar=QLabel(self,objectName="senderAvatar");avatar.setFixedSize(30,30)
            avatar_icon=message.get("sender_avatar_icon") if message.get("show_sender_avatar",True) else None
            if avatar_icon:avatar.setPixmap(avatar_icon.pixmap(30,30))
            self.sender_avatar=avatar;row.addWidget(avatar,0,Qt.AlignBottom)
        content.addWidget(sender)
        try:reply=json.loads(message.get("reply_json") or "null")
        except (TypeError,json.JSONDecodeError):reply=None
        if reply:
            quote=(reply.get("text") or "[Medya veya dosya]").replace("\n"," ").strip()
            if len(quote)>140:quote=quote[:137]+"…"
            self.reply_quote=QLabel(f"↪ {reply.get('sender') or 'Mesaj'}\n{quote}",self.bubble,objectName="replyQuote");self.reply_quote.setWordWrap(True);content.addWidget(self.reply_quote)
        content.addWidget(body)
        if not body_text:body.hide()
        self.attachment_buttons=[]
        for attachment in attachments:
            card=QFrame(self.bubble,objectName="attachmentCard")
            layout=QVBoxLayout(card);layout.setContentsMargins(9,7,9,7);layout.setSpacing(4)
            mime=str(attachment.get("mime_type") or "").lower()
            if mime.startswith("image/") and attachment.get("peer_id") is not None and attachment.get("message_id"):
                preview=ClickableImagePreview("Görsel önizlemesi yükleniyor…",card,objectName="imagePreview")
                preview.setAlignment(Qt.AlignCenter);preview.setMinimumSize(160,100);preview.setMaximumSize(420,280);preview.setCursor(Qt.PointingHandCursor)
                preview.setProperty("mediaLoaded",False);preview.setProperty("mediaRequest",{"peer_id":attachment.get("peer_id"),"message_id":attachment.get("message_id"),"media_json":json.dumps(attachment,ensure_ascii=False)});layout.addWidget(preview)
            name=QLabel(safe_filename(attachment.get("name")),card,objectName="attachmentName")
            name.setTextFormat(Qt.PlainText);name.setWordWrap(True);layout.addWidget(name)
            info=QLabel(format_size(attachment.get("size"))+(f" · {attachment['mime_type']}" if attachment.get("mime_type") else ""),card,objectName="muted")
            info.setTextFormat(Qt.PlainText);info.setWordWrap(True);layout.addWidget(info)
            button=QPushButton("İndir / Bilgisayara kaydet…",card,objectName="attachmentDownload")
            button.setAccessibleName("Dosyayı indir: "+name.text())
            available=attachment.get("peer_id") is not None and bool(attachment.get("message_id"))
            button.setEnabled(available)
            button.setToolTip("Dosyayı Telegram üzerinden kaydet" if available else "Bu gönderi için dosya indirme bağlantısı kayıtlı değil; alıcı sohbetinden açabilirsiniz.")
            request={"peer_id":attachment.get("peer_id"),"message_id":attachment.get("message_id"),"media_json":json.dumps(attachment,ensure_ascii=False)}
            button.clicked.connect(lambda checked=False,target=request:self.downloadRequested.emit(target))
            self.attachment_buttons.append(button);layout.addWidget(button);content.addWidget(card)
        footer_row=QHBoxLayout();footer_row.addStretch();footer_row.addWidget(footer);footer_row.addWidget(ticks);content.addLayout(footer_row)
        self.reactions_label=QLabel("",self.bubble,objectName="reactionSummary")
        self.reactions_label.setTextFormat(Qt.PlainText);self.reactions_label.setWordWrap(True)
        content.addWidget(self.reactions_label)
        self.set_reactions(message.get("reactions_json"))
        if self.outgoing: row.addStretch(1); row.addWidget(self.bubble)
        else: row.addWidget(self.bubble); row.addStretch(1)
        # Selectable QLabels otherwise consume right-clicks with a native text menu.
        # Intercept the context event only; normal text selection remains available.
        for widget in [self, *self.findChildren(QWidget)]:
            widget.installEventFilter(self)

    def set_reactions(self,value):
        try:rows=json.loads(value) if isinstance(value,str) else value or []
        except (TypeError,ValueError):rows=[]
        if not isinstance(rows,list):rows=[]
        rows=[r for r in rows if isinstance(r,dict) and r.get("emoji")]
        self.reactions_label.setText("  ".join(f"{r['emoji']} {r.get('count',0)}"+(" ✓" if r.get("chosen") else "") for r in rows))
        own=[r["emoji"] for r in rows if r.get("chosen")]
        self.reactions_label.setToolTip("Tepkileriniz: "+" ".join(own) if own else "Mesaj tepkileri")
        self.reactions_label.setVisible(bool(rows))
        self.message["reactions_json"]=json.dumps(rows,ensure_ascii=False)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ContextMenu:
            pos = event.globalPos()
            if event.reason() == event.Reason.Keyboard:
                pos = watched.mapToGlobal(watched.rect().center())
            event.accept()
            self.contextMenuRequested.emit(pos)
            return True
        return super().eventFilter(watched, event)

    def set_bubble_limit(self, width):
        max_content=max(180,width-26);metrics=self.body.fontMetrics()
        longest=max((metrics.horizontalAdvance(line) for line in self.body.text().splitlines()),default=0)
        has_media=bool(self.attachment_buttons)
        content_width=min(max_content,max(220 if has_media else 42,longest+2))
        self.bubble.setMaximumWidth(max_content+26);self.body.setFixedWidth(content_width)
        self.sender.setMaximumWidth(max_content);self.footer.setMaximumWidth(max_content)
        bounds=metrics.boundingRect(QRect(0,0,content_width,10000),Qt.TextWordWrap,self.body.text())
        self.body.setMinimumHeight(max(metrics.height(),bounds.height()+4))
        self.bubble.layout().activate();self.layout().activate();self.adjustSize()

    def set_delivery_read(self,read=True):
        if self.outgoing:self.ticks.setText("✓✓" if read else "✓")


class MessageListWidget(QListWidget):
    def __init__(self):
        super().__init__(); self.setObjectName("messages"); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel); self.setWordWrap(True); self.setSpacing(1)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_bubble_widths)
    def _sync_bubble_widths(self):
        width = max(240, int(self.viewport().width() * .76))
        for index in range(self.count()):
            item = self.item(index); row = self.itemWidget(item)
            if row:
                row.set_bubble_limit(width); item.setSizeHint(QSize(max(1, self.viewport().width()), row.sizeHint().height() + 8))
