"""Chat selection, history, message composition and interactions."""
from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from PySide6.QtCore import QItemSelectionModel, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QLabel, QListWidgetItem, QMessageBox
from qasync import asyncSlot

if __package__:
    from .media import decode_media, media_metadata
    from .telegram_service import edit_metadata, edited_message_row, emoji_key, reaction_rows
    from .ui_common import _format_chat_datetime, _icon_size, _line_icon, _local_datetime
    from .ui_widgets import MessageBubbleRow
else:  # Direct and frozen entry points
    from media import decode_media, media_metadata
    from telegram_service import edit_metadata, edited_message_row, emoji_key, reaction_rows
    from ui_common import _format_chat_datetime, _icon_size, _line_icon, _local_datetime
    from ui_widgets import MessageBubbleRow


class ChatView:
    """Chat selection, history, message composition and interactions."""

    def _init_chat_view(self):
        self.selected_peer = None
        self.reply_to = None
        self.reply_context = None
        self.current_collection = None
        self.active_collection_ids = []
        self.active_recipient_ids = []
        self.context_mode = "none"
        self._chat_open_generation = 0
        self.active_kind = "Tümü"
        self._avatar_cache = {}
        self._avatar_loading = set()
        self.pending_chat_files = []
        self._pasted_clipboard_files = set()
        self._uploading_clipboard_files = set()
        self._direct_sends = 0

    def set_filter(self,key):
        self.active_kind=key
        for k,b in self.filters.items():b.setChecked(k==key)
        self.refresh_chats()

    def refresh_chats(self):
        if not hasattr(self,"chat_list"):return
        current_item=self.chat_list.currentItem();current_peer=current_item.data(Qt.UserRole) if current_item else None
        selected_peers={int(item.data(Qt.UserRole)) for item in self.chat_list.selectedItems() if item.data(Qt.UserRole) is not None}
        if not selected_peers and self.selected_peer is not None:selected_peers={int(self.selected_peer)}
        keep_peer=int(self.selected_peer) if self.selected_peer is not None else None;self.chat_list.blockSignals(True)
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
            stamp=_format_chat_datetime(row.get('last_message_at'))
            receipt="✓✓ " if row.get("last_message_outgoing") and row.get("last_message_read") else "✓ " if row.get("last_message_outgoing") else ""
            title=f"{row['title']}\n{receipt}{row.get('last_message') or row['kind']} · {stamp}"
            if row['hidden']:title="◌  "+title
            item=QListWidgetItem(title);item.setData(Qt.UserRole,row['peer_id']);item.setToolTip(row['title']);item.setIcon(self._avatar_cache.get(int(row['peer_id'])) or self._avatar_icon(row['title']));item.setSizeHint(QSize(0,self._chat_row_height()));self.chat_list.addItem(item)
            peer_id=int(row['peer_id'])
            if peer_id in selected_peers:item.setSelected(True)
            if peer_id==current_peer:self.chat_list.setCurrentItem(item,QItemSelectionModel.NoUpdate)
            elif peer_id==keep_peer and current_peer is None:self.chat_list.setCurrentItem(item,QItemSelectionModel.NoUpdate)
        self.chat_list.blockSignals(False)
        if rows:QTimer.singleShot(0,self._queue_visible_avatars)

    def _chat_row_height(self):
        base={"Rahat":76,"Standart":66,"Yoğun":56}.get(self.density.currentText() if hasattr(self,"density") else "Rahat",66)
        return round(base*(self.font_size.value()/13)) if hasattr(self,"font_size") else base

    def _avatar_icon(self,title):
        seed=sum((i+1)*ord(ch) for i,ch in enumerate(title));palette=["#bb3151","#7356b8","#3478a8","#287c6b","#bd7440","#546a9f"];color=QColor(palette[seed%len(palette)]);pix=QPixmap(38,38);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.setBrush(color);p.setPen(Qt.NoPen);p.drawEllipse(1,1,36,36);p.setPen(Qt.white);font=QFont("Segoe UI",11,QFont.Bold);p.setFont(font);p.drawText(pix.rect(),Qt.AlignCenter,"".join(x[0] for x in title.split()[:2]).upper()[:2] or "?");p.end();return QIcon(pix)

    def _photo_avatar_icon(self,data):
        source=QPixmap()
        if not source.loadFromData(data):return None
        side=64;scaled=source.scaled(side,side,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
        pix=QPixmap(side,side);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);clip=QPainterPath();clip.addEllipse(1,1,side-2,side-2);p.setClipPath(clip)
        p.drawPixmap((side-scaled.width())//2,(side-scaled.height())//2,scaled);p.end();return QIcon(pix)

    def _queue_visible_avatars(self):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():return
        try:loop=asyncio.get_running_loop()
        except RuntimeError:return
        for index in range(self.chat_list.count()):
            item=self.chat_list.item(index)
            if not self.chat_list.visualItemRect(item).intersects(self.chat_list.viewport().rect()):continue
            peer_id=int(item.data(Qt.UserRole)) if item.data(Qt.UserRole) is not None else None
            if peer_id is not None and peer_id not in self._avatar_cache and peer_id not in self._avatar_loading:
                loop.create_task(self._ensure_chat_avatar(peer_id))

    async def _ensure_chat_avatar(self,peer_id):
        if peer_id in self._avatar_cache or peer_id in self._avatar_loading:return
        service=self.telegram
        if not service or not service.client or not service.client.is_connected():return
        self._avatar_loading.add(peer_id)
        try:
            data=await service.download_profile_photo(peer_id)
            icon=self._photo_avatar_icon(data) if data else None
            if self.telegram is service:
                self._avatar_cache[peer_id]=icon
                for index in range(self.chat_list.count()):
                    item=self.chat_list.item(index)
                    if item.data(Qt.UserRole)==peer_id:
                        item.setIcon(icon or self._avatar_icon((self.store.chat(peer_id) or {}).get("title","Telegram")))
                if self.selected_peer==peer_id and icon:self.chat_avatar.setPixmap(icon.pixmap(42,42))
                if icon:self._update_message_avatar_for_peer(peer_id,icon)
        except Exception:
            if self.telegram is service:self._avatar_cache[peer_id]=None
        finally:self._avatar_loading.discard(peer_id)

    def _update_message_avatar_for_peer(self,peer_id,icon):
        if self.context_mode!="chat":return
        for index in range(self.messages.count()):
            item=self.messages.item(index);data=item.data(Qt.UserRole) or {};kind=data.get("chat_kind")
            avatar_peer=data.get("sender_id") if kind in ("Grup","Kanal") else self.selected_peer if kind in ("Kişi","Bot") else None
            if avatar_peer is None or int(avatar_peer)!=int(peer_id):continue
            data["sender_avatar_icon"]=icon;item.setData(Qt.UserRole,data)
            row=self.messages.itemWidget(item);avatar=getattr(row,"sender_avatar",None) if row else None
            if avatar and data.get("show_sender_avatar",True):avatar.setPixmap(icon.pixmap(30,30))

    def _activate_chat_context(self,peer_id,owner_collection=None):
        row=self.store.chat(peer_id)
        if not row:return
        self._chat_open_generation+=1;generation=self._chat_open_generation
        self.context_mode="chat";self.selected_peer=int(peer_id);self.active_collection_ids=[];self.active_recipient_ids=[int(peer_id)];self.current_collection=owner_collection
        self._clear_reply();self._clear_chat_files();self.older_messages_btn.setEnabled(True);self.message_search.setEnabled(True)
        self.chat_title.setText(row['title']);self.chat_meta.setText(f"{row['kind']} · {row.get('username') or 'Telegram'}");self.chat_avatar.setPixmap((self._avatar_cache.get(int(peer_id)) or self._avatar_icon(row['title'])).pixmap(42,42))
        try:asyncio.get_running_loop().create_task(self._ensure_chat_avatar(int(peer_id)))
        except RuntimeError:pass
        self.message_input.send_on_enter=True;self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin… (Enter: gönder, Shift+Enter: yeni satır)");self.messages.clear()
        asyncio.create_task(self._open_telegram_chat(int(peer_id),generation))

    def _chat_menu(self,pos):
        item=self.chat_list.itemAt(pos)
        if not item:return
        peers=self._chat_peers_for_context(item)
        if not peers:return
        menu=self._new_menu(self.chat_list);hide=menu.addAction("Seçilileri gizle");add=menu.addAction("Seçilileri klasöre ekle");bulk=menu.addAction("Seçililere toplu mesaj gönder")
        notifications=menu.addAction("Bildirim ayarları…") if len(peers)==1 else None
        chosen=menu.exec(self.chat_list.mapToGlobal(pos))
        if notifications is not None and chosen==notifications:
            self._open_chat_notification_settings(peers[0])
            return
        if chosen==hide:self.store.set_hidden(peers,True);self.refresh_chats()
        elif chosen==add:
            cs=self.store.collections();names=[" › ".join(self.store.collection_path(c['id'])) for c in cs]
            if not cs:QMessageBox.information(self,"Klasör yok","Önce Klasörler sekmesinden bir klasör oluşturun.");return
            name,ok=QInputDialog.getItem(self,"Klasöre ekle","Hedef klasör:",names,0,False)
            if ok:self.store.add_chats_to_collection(cs[names.index(name)]['id'],peers);self.refresh_tree();self.statusBar().showMessage(f"{len(peers)} sohbet klasöre eklendi",5000)
        elif chosen==bulk:
            self._activate_chat_selection(peers);self._start_bulk(direct_peer_ids=peers)

    def _chat_peers_for_context(self,item):
        if item.data(Qt.UserRole) is None:return []
        # Right-clicking an unselected row makes it the sole target. Right-clicking
        # an already selected row preserves the current multi-selection.
        if not item.isSelected():
            self.chat_list.clearSelection()
            self.chat_list.setCurrentItem(item,QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
        return [int(i.data(Qt.UserRole)) for i in self.chat_list.selectedItems() if i.data(Qt.UserRole) is not None]

    def _chat_selected(self):
        peers=[int(item.data(Qt.UserRole)) for item in self.chat_list.selectedItems() if item.data(Qt.UserRole) is not None]
        if len(peers)>1:
            self._activate_chat_selection(peers);return
        if len(peers)==1:
            self._activate_chat_context(peers[0]);return
        if self.context_mode=="selection":
            self._chat_open_generation+=1;self.context_mode="none";self.selected_peer=None;self.active_recipient_ids=[];self._clear_reply();self.messages.clear();self.chat_title.setText("Sohbet seçin");self.chat_meta.setText("Bir sohbet seçtiğinizde geçmişi burada görünür")

    def _activate_chat_selection(self,peer_ids):
        peers=list(dict.fromkeys(int(peer_id) for peer_id in peer_ids))
        if len(peers)<2:return
        self._chat_open_generation+=1;self.context_mode="selection";self.selected_peer=None;self.current_collection=None;self.active_collection_ids=[];self.active_recipient_ids=peers;self._clear_reply();self._clear_chat_files();self.older_messages_btn.setEnabled(False);self.message_search.setEnabled(False)
        self.chat_title.setText(f"{len(peers)} sohbet seçildi");self.chat_meta.setText("Sağ tıklayarak klasöre ekleyin veya toplu mesaj gönderin")
        self.message_input.send_on_enter=False;self.message_input.setPlaceholderText("Seçili sohbetlere gönderilecek mesaj… (Enter: yeni satır)");self.messages.clear()

    async def _open_telegram_chat(self,peer_id,generation=None):
        generation=self._chat_open_generation if generation is None else generation
        await self.load_history(peer_id,generation=generation)
        if generation!=self._chat_open_generation or self.context_mode!="chat" or self.selected_peer!=peer_id:return
        if self.telegram:
            rows=self.store.messages(peer_id,1)
            if rows:
                try:await self.telegram.mark_read(peer_id,rows[-1]['message_id']);self.store.clear_unread(peer_id);self.refresh_chats()
                except Exception:self.statusBar().showMessage("Okundu durumu Telegram tarafından onaylanmadı",5000)

    async def load_history(self,peer_id,before=None,generation=None,reply_context=None):
        if not self.telegram:return
        generation=self._chat_open_generation if generation is None else generation
        try:
            rows=await self.telegram.history(peer_id,50,before)
            known={int(row["message_id"]):row for row in self.store.messages(peer_id,500)}
            known.update({int(row["message_id"]):row for row in rows})
            for row in rows:
                reply_id=row.get("reply_to_message_id")
                if reply_id is None:continue
                target=reply_context if reply_context and int(reply_context.get("message_id",-1))==int(reply_id) else known.get(int(reply_id))
                if target:
                    row["reply_json"]=json.dumps({"sender":target.get("sender_name") or target.get("sender") or "Mesaj","text":target.get("text") or "[Medya veya dosya]"},ensure_ascii=False)
                else:row["reply_json"]=json.dumps({"sender":"Yanıtlanan mesaj","text":f"Mesaj #{reply_id}"},ensure_ascii=False)
            self.store.cache_messages([{k:r.get(k) for k in ['peer_id','message_id','sender_id','sender_name','text','date','outgoing','media_json','reactions_json','reply_json','edit_date','edit_hidden']} for r in rows])
            if generation==self._chat_open_generation and self.context_mode=="chat" and self.selected_peer==peer_id:self._render_messages(peer_id)
        except Exception as e:
            if generation==self._chat_open_generation and self.selected_peer==peer_id:self.statusBar().showMessage(f"Mesaj geçmişi yüklenemedi: {e}",10000)

    def load_older_messages(self):
        if self.selected_peer is None or not self.telegram:return
        peer_id=self.selected_peer;generation=self._chat_open_generation;rows=self.store.messages(peer_id,100)
        if rows:asyncio.create_task(self.load_history(peer_id,rows[0]['message_id'],generation))

    def _render_messages(self,peer_id):
        if self.context_mode!="chat" or self.selected_peer!=peer_id:return
        chat=self.store.chat(peer_id) or {};kind=chat.get("kind")
        rows=self.store.messages(peer_id,100)
        read_checker=getattr(self.telegram,"is_message_read",None)
        previous=None
        for m in rows:
            m["chat_kind"]=kind
            if read_checker and m.get("outgoing"):
                m["read"]=read_checker(peer_id,m["message_id"])
            if kind in ("Grup","Kanal","Kişi","Bot") and not m.get("outgoing"):
                previous_time=_local_datetime(previous.get("date")) if previous else None
                current_time=_local_datetime(m.get("date"))
                same_cluster=bool(previous_time and current_time and 0<=(current_time-previous_time).total_seconds()<=300)
                same_sender=bool(same_cluster and previous and not previous.get("outgoing") and (kind not in ("Grup","Kanal") or previous.get("sender_id")==m.get("sender_id")))
                m["show_sender_avatar"]=not same_sender
            previous=m

        view=self.messages
        # Reuse rows across live updates, including when the oldest row drops
        # off the end of the 100-message history window.
        positions={m["message_id"]: index for index,m in enumerate(rows)}
        retained=[]
        stale=[]
        for index in range(view.count()):
            data=view.item(index).data(Qt.UserRole) or {}
            position=positions.get(data.get("message_id")) if data.get("peer_id")==peer_id else None
            if position is None:
                stale.append(index)
            else:
                retained.append(position)

        updates_enabled=view.updatesEnabled()
        view.setUpdatesEnabled(False)
        try:
            if retained!=sorted(set(retained)):
                # Search results may be ordered differently from cached history.
                view.clear()
            else:
                for index in reversed(stale):
                    view.takeItem(index)
            for index,message in enumerate(rows):
                item=view.item(index)
                current=item.data(Qt.UserRole) if item else None
                if not current or current["message_id"]!=message["message_id"]:
                    item=QListWidgetItem()
                    view.insertItem(index,item)
                else:
                    current.pop("sender_avatar_icon",None)
                    if current==message and view.itemWidget(item):
                        continue
                if message.get("show_sender_avatar"):
                    sender_id=message.get("sender_id") if kind in ("Grup","Kanal") else peer_id
                    icon=self._avatar_cache.get(int(sender_id)) if sender_id else None
                    message["sender_avatar_icon"]=icon or self._avatar_icon(message.get("sender_name") or "Telegram")
                self._set_message_bubble(item,message)
            view.scrollToBottom()
        finally:
            view.setUpdatesEnabled(updates_enabled)

    def _append_message_bubble(self,message):
        message=dict(message)
        if message.get("chat_kind") is None and message.get("peer_id") is not None:
            message["chat_kind"]=(self.store.chat(message["peer_id"]) or {}).get("kind")
        item=QListWidgetItem()
        self.messages.addItem(item)
        self._set_message_bubble(item,message)

    def _set_message_bubble(self,item,message):
        item.setData(Qt.UserRole,message)
        row=MessageBubbleRow(message,self.messages.viewport())
        row.set_bubble_limit(max(240,int(self.messages.viewport().width()*.76)))
        self.messages.setItemWidget(item,row)
        row.contextMenuRequested.connect(lambda global_pos,target=item:self._message_menu(self.messages.viewport().mapFromGlobal(global_pos),item=target))
        row.downloadRequested.connect(lambda target:asyncio.create_task(self._download_message(target)))
        for preview in row.findChildren(QLabel,"imagePreview"):
            request=preview.property("mediaRequest")
            if request:
                preview.clicked.connect(lambda target=preview,media=request:self._show_fullscreen_preview(target,media))
                self._schedule_visible_previews()
        if row.is_group and not row.outgoing and item.data(Qt.UserRole).get("sender_id"):
            sender_id=int(item.data(Qt.UserRole)["sender_id"])
            if sender_id not in self._avatar_cache and self.telegram:
                try:asyncio.get_running_loop().create_task(self._ensure_chat_avatar(sender_id))
                except RuntimeError:pass
        item.setSizeHint(QSize(max(1,self.messages.viewport().width()),row.sizeHint().height()+8))

    def _set_reply(self,message):
        self.reply_to=message.get("message_id");self.reply_context={"sender":message.get("sender_name") or "Mesaj","text":message.get("text") or "[Medya veya dosya]"}
        preview=self.reply_context["text"].replace("\n"," ").strip()
        if len(preview)>180:preview=preview[:177]+"…"
        self.reply_preview.setText(f"Yanıtlanıyor: {self.reply_context['sender']}\n{preview}");self.reply_preview_frame.show();self.message_input.setFocus()

    def _clear_reply(self):
        self.reply_to=None;self.reply_context=None
        if hasattr(self,"reply_preview_frame"):self.reply_preview_frame.hide();self.reply_preview.clear()

    def _show_emoji_picker(self):
        menu=self._new_menu(self.emoji_button)
        emojis=["😀","😃","😄","😁","😅","😂","🙂","😉","😊","😍","🥰","😘","😎","🤔","🙃","😭","😢","😡","👍","👎","👏","🙏","❤️","🔥","🎉","✅","📌","💯"]
        for emoji in emojis:
            action=menu.addAction(emoji);action.triggered.connect(lambda checked=False,value=emoji:self.message_input.insertPlainText(value))
        menu.exec(self.emoji_button.mapToGlobal(self.emoji_button.rect().bottomLeft()))

    @asyncSlot()
    async def send_message(self):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():QMessageBox.information(self,"Telegram bağlı değil","Mesaj göndermek için Telegram hesabını bağlayın.");return
        text=self.message_input.toPlainText().strip()
        if not text and not self.pending_chat_files:return
        if self.context_mode in ("collection","selection"):
            self._start_bulk(collection_ids=self.active_collection_ids,direct_peer_ids=self.active_recipient_ids,preserve_view=True,initial_message=text,initial_files=list(self.pending_chat_files));return
        if self.context_mode!="chat" or self.selected_peer is None:QMessageBox.information(self,"Sohbet seçin","Önce bir Telegram sohbeti veya klasör seçin.");return
        peer_id=self.selected_peer;generation=self._chat_open_generation;files=list(self.pending_chat_files);sent_reply_context={**self.reply_context,"message_id":self.reply_to} if self.reply_context else None
        uploaded=False
        self._direct_sends += 1
        if files:self._uploading_clipboard_files.update(p for p in files if p in self._pasted_clipboard_files)
        try:
            sent=await self.telegram.send_files(peer_id,files,caption=text,progress_callback=self._upload_progress,reply_to=self.reply_to) if files else await self.telegram.send_text(peer_id,text,reply_to=self.reply_to)
            uploaded=True
            last=sent[-1] if isinstance(sent,list) else sent
            if last:
                summary=text or ("Dosya: "+Path(files[-1]).name if files else "Mesaj")
                read_checker=getattr(self.telegram,"is_message_read",lambda _peer,_message:False)
                self.store.update_last_message(peer_id,summary,last.date.isoformat() if getattr(last,"date",None) else datetime.now(timezone.utc).isoformat(),outgoing=True,read=read_checker(peer_id,last.id),message_id=last.id)
                self.refresh_chats()
            if generation!=self._chat_open_generation or self.selected_peer!=peer_id:return
            self.message_input.clear();self._clear_chat_files();self._clear_reply();self.message_input.setPlaceholderText("Mesaj yazın veya dosyaları buraya sürükleyin…");await self.load_history(peer_id,generation=generation,reply_context=sent_reply_context)
        except Exception as e:QMessageBox.warning(self,"Mesaj gönderilemedi",str(e))
        finally:
            self._direct_sends -= 1
            pasted={p for p in files if p in self._pasted_clipboard_files}
            self._uploading_clipboard_files.difference_update(pasted)
            discarded=pasted if uploaded else {p for p in pasted if p not in self.pending_chat_files}
            self._discard_pasted_files(discarded)
            self.statusBar().showMessage("Dosya yüklemesi tamamlandı" if uploaded and files else "",3000)

    def attach_to_chat(self):
        if not self.telegram or self.selected_peer is None:QMessageBox.information(self,"Sohbet seçin","Telegram bağlantısı ve sohbet seçimi gerekli.");return
        paths,_=QFileDialog.getOpenFileNames(self,"Dosya veya medya ekle");self._add_chat_files(paths)

    def _add_chat_files(self,paths):
        for path in paths:
            if Path(path).is_file() and path not in self.pending_chat_files:
                self.pending_chat_files.append(path)
                if Path(path).parent==self._app_data_dir()/"clipboard_images":self._pasted_clipboard_files.add(path)
        self._update_pending_files()

    def _update_pending_files(self):
        if hasattr(self,"pending_files_label"):
            names=[Path(p).name for p in self.pending_chat_files];self.pending_files_label.setText(("Ekler: "+" · ".join(names)) if names else "");self.clear_attachments.setEnabled(bool(names));self.clear_attachments.setVisible(bool(names))

    def _clear_chat_files(self):
        self.pending_chat_files.clear()
        for path in tuple(self._pasted_clipboard_files):
            if path in self._uploading_clipboard_files or path in self._bulk_pasted_files:continue
            try:Path(path).unlink(missing_ok=True)
            except OSError:pass
            self._pasted_clipboard_files.discard(path)
        self._update_pending_files()

    def _discard_pasted_files(self,paths):
        for path in paths:
            try:Path(path).unlink(missing_ok=True)
            except OSError:pass
            self._pasted_clipboard_files.discard(path)

    def _upload_progress(self,current,total):
        self.statusBar().showMessage(f"Dosya yükleniyor: {int(100*current/max(total,1))}%")

    def _message_menu(self,pos,item=None):
        if item is None:item=self.messages.itemAt(pos)
        if not item or not item.data(Qt.UserRole):return
        m=item.data(Qt.UserRole)
        if isinstance(m,dict) and m.get("kind")=="collection_job":
            details=self.store.job_targets(m['job_id'])
            lines=[f"{r['peer_title']} · {r['status']}"+(f" · {r['error']}" if r['error'] else "") for r in details]
            QMessageBox.information(self,"Klasör gönderim durumu","\n".join(lines) or "Alıcı kaydı bulunamadı.");return
        if isinstance(m,dict) and m.get("kind")=="collection_member":
            menu=self._new_menu(self.messages);remove=menu.addAction("Bu klasörden çıkar");chosen=menu.exec(self.messages.viewport().mapToGlobal(pos))
            if chosen==remove and self.current_collection:self.store.remove_chat_from_collection(self.current_collection,m['peer_id']);self._collection_selected(self.tree.currentItem());self.refresh_tree()
            return
        menu=self._new_menu(self.messages)
        menu.setObjectName("messageContextMenu")
        theme=self.theme.currentText()
        dark=theme=="Koyu" or (theme=="Sistem ayarı" and QApplication.palette().color(QPalette.Window).lightness()<128)
        color="#e8edf5" if dark else "#202938"
        muted="#a1adbd" if dark else "#687589"
        size=_icon_size(self.font_size.value())
        def icon(name, destructive=False):
            stroke=("#ff9aa5" if dark else "#a61d35") if destructive else color
            return _line_icon(name,stroke,size,muted,stroke)
        row=self.messages.itemWidget(item)
        selected_text=row.body.selectedText() if isinstance(row,MessageBubbleRow) else ""
        reply=menu.addAction(icon("reply"),"Yanıtla")
        copy=menu.addAction(icon("copy"),"Metni kopyala")
        copy_selection=menu.addAction(icon("copy"),"Seçili metni kopyala") if selected_text else None
        reaction_menu=menu.addMenu(icon("emoji"),"Tepki bırak")
        try:reactions=json.loads(m.get("reactions_json") or "[]")
        except (TypeError,ValueError):reactions=[]
        if not isinstance(reactions,list):reactions=[]
        own={emoji_key(r["emoji"]):r["emoji"] for r in reactions if isinstance(r,dict) and r.get("chosen") and r.get("emoji")}
        choices=["👍","❤️","😂","😮","😢","🙏","🔥","🎉"]
        choices.extend(value for key,value in own.items() if key not in {emoji_key(emoji) for emoji in choices})
        for emoji in choices:
            reaction_action=reaction_menu.addAction(emoji)
            reaction_action.setCheckable(True);reaction_action.setChecked(emoji_key(emoji) in own)
            reaction_action.setToolTip("Tepkiyi kaldırmak için seçin" if reaction_action.isChecked() else "Tepki bırak")
            reaction_action.triggered.connect(lambda checked=False,value=emoji,target=m:asyncio.create_task(self._react_to_message(target,value)))
        download=menu.addAction(icon("download"),"Dosyayı indir…") if decode_media(m.get("media_json")) else None
        edit=delete=None
        if m.get("outgoing"):
            menu.addSeparator()
            edit=menu.addAction(icon("edit"),"Mesajı düzenle")
            delete=menu.addAction(icon("trash",True),"Mesajı sil")
        chosen=menu.exec(self.messages.viewport().mapToGlobal(pos))
        # A dismissed menu returns None. Never let None compare equal to an
        # unavailable action (also None), which previously opened a fake download.
        if chosen is None:return
        if chosen==reply:self._set_reply(m)
        elif chosen==copy:QApplication.clipboard().setText(m.get('text') or "")
        elif copy_selection is not None and chosen==copy_selection:QApplication.clipboard().setText(selected_text)
        elif download is not None and chosen==download:asyncio.create_task(self._download_message(m))
        elif edit is not None and chosen==edit:
            text,ok=QInputDialog.getMultiLineText(self,"Mesajı düzenle","Metin:",m['text'])
            if ok:asyncio.create_task(self._edit_message(m,text))
        elif delete is not None and chosen==delete and QMessageBox.question(self,"Mesajı sil","Telegram'dan da silinsin mi?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:asyncio.create_task(self._delete_message(m))

    async def _react_to_message(self,message,emoji):
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():
            QMessageBox.information(self,"Telegram bağlı değil","Tepki bırakmak için Telegram hesabını bağlayın.");return
        service=self.telegram
        try:
            outcome,reactions=await service.send_reaction(message["peer_id"],message["message_id"],emoji)
        except Exception as e:
            code=str(getattr(e,"message","")).upper()
            detail={"REACTION_INVALID":"Bu tepki sohbet için izinli olmayabilir.","REACTIONS_TOO_MANY":"Bu mesaj izin verilen farklı tepki sınırına ulaştı.","PREMIUM_ACCOUNT_REQUIRED":"Bu tepki için Telegram Premium gerekiyor.","REACTION_EMPTY":"Telegram tepki listesini kabul etmedi."}.get(code,str(e))
            QMessageBox.warning(self,"Tepki gönderilemedi",detail);return
        if self.telegram is not service:return
        if reactions is not None:
            self.store.update_message_reactions(message["peer_id"],message["message_id"],reactions)
            # Preserve the scroll position and search result list, even for older messages.
            for index in range(self.messages.count()):
                item=self.messages.item(index);data=item.data(Qt.UserRole) or {}
                if data.get("kind") or (data.get("peer_id"),data.get("message_id"))!=(message["peer_id"],message["message_id"]):continue
                data["reactions_json"]=json.dumps(reactions,ensure_ascii=False);item.setData(Qt.UserRole,data)
                row=self.messages.itemWidget(item)
                if isinstance(row,MessageBubbleRow):
                    row.set_reactions(reactions)
                    row.set_bubble_limit(max(240,int(self.messages.viewport().width()*.76)))
                    item.setSizeHint(QSize(max(1,self.messages.viewport().width()),row.sizeHint().height()+28))
        status={"added":"eklendi","removed":"kaldırıldı","replaced":"değiştirildi","unchanged":"zaten güncel"}[outcome]
        self.statusBar().showMessage(f"{emoji} tepkisi {status}"+(" · Görünüm güncellenemedi" if reactions is None else ""),5000)

    async def _edit_message(self,m,text):
        service=self.telegram
        if not service:
            QMessageBox.information(self,"Telegram bağlı değil","Mesajı düzenlemek için Telegram hesabını bağlayın.");return
        try:updated=await service.edit_message(m["peer_id"],m["message_id"],text)
        except Exception as e:
            QMessageBox.warning(self,"Düzenleme başarısız",str(e));return
        if self.telegram is not service:return
        if getattr(updated,"edit_date",None):
            self._on_message_edited(edited_message_row(updated,m["peer_id"]))
        else:
            # Do not invent an edit timestamp; the server supplies it.
            try:
                updated=await service.client.get_messages(service._entity(m["peer_id"]),ids=m["message_id"])
                if self.telegram is service and getattr(updated,"edit_date",None):
                    self._on_message_edited(edited_message_row(updated,m["peer_id"]))
            except Exception:
                self.statusBar().showMessage("Mesaj düzenlendi; görünüm henüz güncellenemedi.",5000)

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
                metadata=media_metadata(m)
                reactions=reaction_rows(m)
                self._append_message_bubble({"peer_id":self.selected_peer,"message_id":m.id,"sender_id":getattr(m,"sender_id",None),"sender_name":"Siz" if m.out else str(getattr(m,"sender_id",None) or "Telegram"),"text":m.message or "","date":m.date.isoformat() if m.date else "","outgoing":int(bool(m.out)),"media_json":json.dumps(metadata,ensure_ascii=False) if metadata else None,"reactions_json":json.dumps(reactions,ensure_ascii=False),**edit_metadata(m)})
        except Exception as e:QMessageBox.warning(self,"Arama başarısız",str(e))

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

    def _on_live_message(self,row):
        self.store.cache_messages([{k:row.get(k) for k in ['peer_id','message_id','sender_id','sender_name','text','date','outgoing','media_json','reactions_json','edit_date','edit_hidden']}])
        if not self.store.chat(row['peer_id']):
            self.store.upsert_chats([{"peer_id":row['peer_id'],"access_hash":None,"title":row.get('chat_title') or "Telegram sohbet","kind":row.get("chat_kind") or ("Grup" if row['peer_id']<0 else "Kişi"),"username":None,"can_send":1,"unread_count":0,"last_message":row['text'] or "Medya","last_message_at":row['date'],"last_message_id":row['message_id'],"last_message_outgoing":row['outgoing'],"last_message_read":row.get('read',0)}])
            if self.active_nav == "notifications":
                self._refresh_notification_chats()
        else:self.store.update_last_message(row['peer_id'],row['text'] or "Medya",row['date'],incoming=not row['outgoing'],outgoing=bool(row['outgoing']),read=row.get('read',False),message_id=row['message_id'])
        self.refresh_chats()
        if self.selected_peer==row['peer_id']:self._render_messages(row['peer_id'])
        if not row['outgoing']:self._show_local_notification(row)

    def _on_message_read(self,peer_id,max_message_id):
        """Reflect Telegram's outgoing read receipt in the chat list and open history."""
        if self.store.mark_last_message_read(peer_id,max_message_id):
            self.refresh_chats()
        if self.selected_peer!=peer_id or self.context_mode!="chat":
            return
        for index in range(self.messages.count()):
            item = self.messages.item(index)
            data = item.data(Qt.UserRole) or {}
            message_id = data.get("message_id")
            if (data.get("peer_id") != peer_id or not data.get("outgoing")
                    or data.get("read") or not message_id or message_id > max_message_id):
                continue
            data["read"] = True
            item.setData(Qt.UserRole, data)
            bubble = self.messages.itemWidget(item)
            if bubble:
                bubble.set_delivery_read(True)

    def _on_message_edited(self,row):
        """Edits are not new messages: no unread increment or arrival notification."""
        if not row.get("edit_date"):return
        self.store.update_message_edit(row)
        if self.selected_peer!=row["peer_id"] or self.context_mode!="chat":return
        for index in range(self.messages.count()):
            item=self.messages.item(index);data=item.data(Qt.UserRole) or {}
            if data.get("kind") or (data.get("peer_id"),data.get("message_id"))!=(row["peer_id"],row["message_id"]):continue
            previous=_local_datetime(data.get("edit_date"))
            incoming=_local_datetime(row["edit_date"])
            if previous and (not incoming or previous>incoming):continue
            updated={**data,**{key:row[key] for key in ("text","media_json","edit_date","edit_hidden")}}
            self._set_message_bubble(item,updated)
            break
