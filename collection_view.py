"""Folder tree, selection, membership and invite links."""
from __future__ import annotations
import asyncio
import json
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QColorDialog, QDialog, QInputDialog, QMessageBox, QTreeWidgetItem
from telethon.errors import FloodWaitError

if __package__:
    from .media import bulk_attachment_cards
    from .telegram_service import invite_error_message
    from .ui_common import COLLECTION_ICON_OPTIONS, TREE_ICON_ROLE, TREE_NODE_KIND_ROLE, TREE_OWNER_COLLECTION_ROLE, _line_icon
else:  # Direct and frozen entry points
    from media import bulk_attachment_cards
    from telegram_service import invite_error_message
    from ui_common import COLLECTION_ICON_OPTIONS, TREE_ICON_ROLE, TREE_NODE_KIND_ROLE, TREE_OWNER_COLLECTION_ROLE, _line_icon


class CollectionView:
    """Folder tree, selection, membership and invite links."""

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
                custom_icon=c["icon"] if c["icon"]!="📁" else ""
                label=f"{c['name']}  ({c['chat_count']})"
                item=QTreeWidgetItem([f"{custom_icon}  {label}" if custom_icon else label]);item.setData(0,TREE_ICON_ROLE,None if custom_icon else "folders");item.setData(0,Qt.UserRole,c['id']);item.setData(0,TREE_NODE_KIND_ROLE,"collection");item.setForeground(0,QColor(c['color']));self._tree_items[c['id']]=item
                if parent_item is None:self.tree.addTopLevelItem(item)
                else:parent_item.addChild(item)
                if ("collection",c['id'],None) in selected:
                    item.setSelected(True)
                    self.tree.setCurrentItem(item,0,QItemSelectionModel.NoUpdate)
                for chat in self.store.collection_chats(c['id'],False):
                    if query and query not in chat['title'].casefold():continue
                    chat_item=QTreeWidgetItem([f"{chat['title']}  ·  {chat['kind']}"]);chat_item.setData(0,TREE_ICON_ROLE,"person" if chat['kind']=="Kişi" else "group" if chat['kind'] in ("Grup","Kanal") else "chats");chat_item.setData(0,Qt.UserRole,chat['peer_id']);chat_item.setData(0,TREE_NODE_KIND_ROLE,"chat");chat_item.setData(0,TREE_OWNER_COLLECTION_ROLE,c['id']);chat_item.setToolTip(0,chat['title']);item.addChild(chat_item)
                    if ("chat",chat['peer_id'],c['id']) in selected:
                        chat_item.setSelected(True)
                        self.tree.setCurrentItem(chat_item,0,QItemSelectionModel.NoUpdate)
                append_children(c['id'],item)
                if query:item.setExpanded(True)
        append_children(None)
        self._refresh_ui_icons()
        self.refresh_bulk_collections()

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
        self._clear_reply();self._clear_chat_files();self.older_messages_btn.setEnabled(False);self.message_search.setEnabled(False)
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

    def _render_collection_history(self):
        self.messages.clear()
        rows=self.store.collection_messages(self.active_collection_ids,100)
        for job in reversed(rows):
            body=job['message'] or ""
            try:
                files=json.loads(job.get('files_json') or '[]')
            except (TypeError,json.JSONDecodeError):files=[]
            attachments=bulk_attachment_cards(files,self.store.job_targets(job["id"]))
            if not body and not attachments:body="[Ekli dosya]"
            body+=( "\n\n" if body else "")+f"Teslim durumu: {job.get('sent') or 0}/{job.get('total') or 0} · {job['status']}"
            entry={"kind":"collection_job","job_id":job['id'],"peer_id":None,"message_id":job['id'],"sender_id":None,"sender_name":"Siz · Klasör gönderimi","text":body,"date":job['created_at'],"outgoing":1,"media_json":job.get('files_json'),"attachments":attachments}
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
        dark=self.theme.currentText()=="Koyu" or (self.theme.currentText()=="Sistem ayarı" and QApplication.palette().color(QPalette.Window).lightness()<128)
        icon_color="#e8edf5" if dark else "#202938";muted="#a1adbd" if dark else "#687589"
        def menu_icon(name,danger=False):
            stroke=("#ff9aa5" if dark else "#a61d35") if danger else icon_color
            return _line_icon(name,stroke,18,muted,stroke)
        menu=self._new_menu(self.tree);send=menu.addAction(menu_icon("bulk"),"Seçili klasör/sohbetlere mesaj gönder…");invite=menu.addAction(menu_icon("group"),"Davet bağlantıları oluştur…")
        new=rename=move_action=up_action=down_action=color_action=icon_action=delete=remove=None
        # Folder actions belong to the row under the pointer. Keep them available
        # even when a multi-selection exists for bulk send/invite actions.
        if kind=="collection":
            menu.addSeparator();new=menu.addAction(menu_icon("plus"),"Alt klasör oluştur");rename=menu.addAction(menu_icon("edit"),"Yeniden adlandır");move_action=menu.addAction(menu_icon("folders"),"Başka klasöre taşı…");up_action=menu.addAction(menu_icon("up"),"Sıralamada yukarı al");down_action=menu.addAction(menu_icon("down"),"Sıralamada aşağı al");color_action=menu.addAction(menu_icon("image"),"Renk seç…");icon_action=menu.addAction(menu_icon("chats"),"Simge seç…");delete=menu.addAction(menu_icon("trash",True),"Klasörü sil")
        elif len(nodes)==1 and kind=="chat":
            menu.addSeparator();remove=menu.addAction(menu_icon("close",True),"Sohbeti bu klasörden çıkar")
        chosen=menu.exec(self.tree.mapToGlobal(pos))
        if chosen is None:return
        if chosen==send:
            collection_ids,peer_ids=self._tree_target_ids(nodes)
            self._collection_selected(item)
            self._start_bulk(collection_ids=collection_ids,direct_peer_ids=peer_ids,preserve_view=True)
        elif chosen==invite:
            collection_ids,peer_ids=self._tree_target_ids(nodes)
            self._start_invite_link_creation(collection_ids,peer_ids)
        elif chosen==new:
            name,ok=QInputDialog.getText(self,"Alt klasör","Klasör adı:")
            if ok and name:self.store.create_collection(name,int(cid));self.refresh_tree()
        elif chosen==rename:
            folder=next((row for row in self.store.collections() if int(row["id"])==int(cid)),None)
            if not folder:
                self.statusBar().showMessage("Klasör artık bulunamadı; klasör listesini yenileyin",5000);return
            name,ok=QInputDialog.getText(self,"Klasörü yeniden adlandır","Yeni ad:",text=folder["name"])
            if ok:
                try:
                    name=name.strip()
                    if not name:raise ValueError("Klasör adı boş olamaz")
                    self.store.rename_collection(int(cid),name);self.current_collection=int(cid);self.refresh_tree()
                    renamed_item=self._tree_items.get(int(cid))
                    if renamed_item:
                        self.tree.clearSelection();renamed_item.setSelected(True);self.tree.setCurrentItem(renamed_item)
                    self.statusBar().showMessage(f'Klasör "{name}" olarak yeniden adlandırıldı',5000)
                except Exception as e:QMessageBox.warning(self,"Klasör yeniden adlandırılamadı",str(e))
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
            chooser=QInputDialog(self);chooser.setWindowTitle("Klasör simgesi");chooser.setLabelText("Geniş emoji listesinden seçin veya emoji yazın. Windows emoji paneli: Win + .");chooser.setComboBoxItems(COLLECTION_ICON_OPTIONS);chooser.setComboBoxEditable(True);chooser.setTextValue("📁")
            if chooser.exec()==QDialog.Accepted and chooser.textValue().strip():
                icon=chooser.textValue().strip()
                with self.store.db() as db:db.execute("UPDATE collections SET icon=? WHERE id=?",(icon,int(cid)))
                self.refresh_tree()

    def _start_invite_link_creation(self,collection_ids,peer_ids):
        """Resolve selected folder/chat targets and start creating their invite links."""
        targets={}
        collection_rows={int(c["id"]):c for c in self.store.collections()}
        for cid in collection_ids:
            if int(cid) not in collection_rows:continue
            root_path_ids=self.store.collection_path_ids(int(cid))
            for chat in self.store.collection_chats(int(cid),True):
                peer_id=int(chat["peer_id"]);title=chat["title"]
                paths=[self.store.collection_path(owner_id) for owner_id in self.store.chat_collection_ids(peer_id)
                       if self.store.collection_path_ids(owner_id)[:len(root_path_ids)]==root_path_ids]
                if not paths:paths=[self.store.collection_path(int(cid))]
                target=targets.setdefault(peer_id,{"title":title,"paths":[],"access_hash":chat.get("access_hash")})
                target["paths"].extend(path+[title] for path in paths)
        for peer_id in peer_ids:
            peer_id=int(peer_id);chat=self.store.chat(peer_id)
            if not chat:continue
            paths=[self.store.collection_path(owner_id) for owner_id in self.store.chat_collection_ids(peer_id)] or [[]]
            target=targets.setdefault(peer_id,{"title":chat["title"],"paths":[],"access_hash":chat.get("access_hash")})
            target["paths"].extend(path+[chat["title"]] for path in paths)
        if not targets:
            QMessageBox.information(self,"Davet bağlantısı oluştur","Seçilen klasörlerde oluşturulacak sohbet bulunamadı.");return
        if not self.telegram or not self.telegram.client or not self.telegram.client.is_connected():
            QMessageBox.warning(self,"Telegram bağlı değil","Davet bağlantısı oluşturmak için önce Telegram hesabını bağlayın.");return
        if getattr(self,"_invite_task",None) and not self._invite_task.done():
            QMessageBox.information(self,"Davet bağlantıları","Bağlantılar zaten hazırlanıyor.");return
        self._invite_task=asyncio.create_task(self._create_invite_links(targets))

    async def _create_invite_links(self,targets):
        service=self.telegram
        self.statusBar().showMessage(f"{len(targets)} sohbet için davet bağlantısı hazırlanıyor…")
        invite_by_peer={};stop_reason=None
        for index,(peer_id,target) in enumerate(targets.items(),1):
            if self.telegram is not service or not service or not service.client or not service.client.is_connected():
                self.statusBar().showMessage("Telegram bağlantısı değişti; işlem durduruldu.",5000);return
            if int(peer_id)>=0:
                invite_by_peer[peer_id]={"error":"Kişi ve bot sohbetleri için davet bağlantısı desteklenmiyor."};continue
            if stop_reason:
                invite_by_peer[peer_id]={"error":stop_reason};continue
            self.statusBar().showMessage(f"Davet bağlantıları: {index}/{len(targets)}")
            try:
                link=await service.export_chat_invite_link(peer_id,access_hash=target.get("access_hash"))
                invite_by_peer[peer_id]={"link":link}
            except FloodWaitError as e:
                stop_reason=invite_error_message(e)
                invite_by_peer[peer_id]={"error":stop_reason}
            except Exception as e:
                invite_by_peer[peer_id]={"error":invite_error_message(e)}
        if self.telegram is not service or not service.client or not service.client.is_connected():
            self.statusBar().showMessage("Telegram bağlantısı değişti; işlem durduruldu.",5000);return
        entries=[]
        for peer_id,target in targets.items():
            for path in dict.fromkeys(tuple(p) for p in target["paths"]):
                entries.append({"path":list(path),**invite_by_peer[peer_id]})
        successes=sum(bool(result.get("link")) for result in invite_by_peer.values())
        self.statusBar().showMessage(f"Davet bağlantıları: {successes}/{len(targets)} başarılı",5000)
        dlg=self._new_invite_links_dialog(entries);dlg.exec()

    def _dropped_chats(self,cid,peer_ids):
        self.store.add_chats_to_collection(cid,peer_ids);self.refresh_tree();self.statusBar().showMessage(f"{len(peer_ids)} sohbet klasöre eklendi",4000)
