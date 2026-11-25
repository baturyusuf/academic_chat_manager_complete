import os, asyncio, pytest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QBuffer, QIODevice
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from academic_chat_manager.main import MainWindow

def test_main_window_starts_with_real_empty_data(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    # Use a temporary SQLite database, never the user's profile during the test.
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();assert w.windowTitle()=="Akademik Sohbet Yöneticisi";assert w.store.chats()==[];w.close()
def test_collection_tree_and_settings_navigation(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui2.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();root=w.store.create_collection("Üniversite");w.store.create_collection("Yapay Zekâ",root);w.refresh_tree()
    assert w.tree.topLevelItemCount()==1 and w.tree.topLevelItem(0).childCount()==1
    w.navigate("settings");assert w.center_stack.currentWidget() is w.settings_page
    w.theme.setCurrentText("Koyu");assert w.store.preference("appearance/theme")=="Koyu"
    w.close()

def test_font_change_is_immediate_and_theme_change_is_independent(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui3.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.font_size.setValue(17)
    assert app.font().pointSize()==17
    w.theme.setCurrentText("Koyu")
    assert app.font().pointSize()==17 and w.store.preference('appearance/font_size')==17
    assert "#151922" in w.styleSheet()
    assert w.chat_title.font().pointSize()==17
    w.close()

def test_right_click_targets_context_row_and_preserves_multi_selection(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui4.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    rows=[]
    for peer_id,title in ((-101,"Birinci"),(-102,"İkinci")):
        rows.append({"peer_id":peer_id,"access_hash":1,"title":title,"kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None})
    w.store.upsert_chats(rows);w.refresh_chats()
    w.chat_list.blockSignals(True)
    first,second=w.chat_list.item(0),w.chat_list.item(1)
    first.setSelected(True)
    assert w._chat_peers_for_context(second)==[-102]
    first.setSelected(True);second.setSelected(True)
    assert set(w._chat_peers_for_context(first))=={-101,-102}
    folder=w.store.create_collection("Test klasörü")
    w.store.add_chats_to_collection(folder,w._chat_peers_for_context(first))
    assert {r['peer_id'] for r in w.store.collection_chats(folder)}=={-101,-102}
    w.close()

def test_long_chat_messages_use_wrapped_bubble_rows(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui5.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.resize(1250,800);w.selected_peer=-201;w.context_mode="chat"
    text="Arkadaşlar merhaba, yarınki Yapay Zekâ Uygulamaları dersi saat 13.00’te D-204 numaralı sınıfta yapılacaktır. Lütfen zamanında gelmeyi unutmayın. Ders notlarını ve ek materyalleri de aşağıda paylaşıyorum."
    w.store.cache_messages([{"peer_id":-201,"message_id":1,"sender_id":1,"sender_name":"Yusuf","text":text,"date":"2026-11-18T09:45:00","outgoing":1,"media_json":None}])
    w._render_messages(-201);app.processEvents()
    item=w.messages.item(0);bubble=w.messages.itemWidget(item)
    assert bubble is not None and bubble.body.wordWrap()
    assert w.messages.horizontalScrollBarPolicy()==main.Qt.ScrollBarAlwaysOff
    assert item.sizeHint().height()>=bubble.sizeHint().height()
    w.close()

def test_collection_tree_ctrl_selection_unions_folders_and_group_nodes(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui6.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    chats=[]
    for peer,title in ((-301,"A alt grubu"),(-302,"B grubu"),(-303,"X grubu")):
        chats.append({"peer_id":peer,"access_hash":1,"title":title,"kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None})
    w.store.upsert_chats(chats)
    folder_a=w.store.create_collection("A");folder_child=w.store.create_collection("A alt klasör",folder_a);folder_x=w.store.create_collection("X");folder_z=w.store.create_collection("Z")
    w.store.add_chats_to_collection(folder_child,[-301]);w.store.add_chats_to_collection(folder_x,[-303]);w.store.add_chats_to_collection(folder_z,[-302]);w.refresh_tree()
    item_a=w._tree_items[folder_a];item_x=w._tree_items[folder_x]
    group_b=next(item for item in (w._tree_items[folder_z].child(i) for i in range(w._tree_items[folder_z].childCount())) if item.data(0,main.TREE_NODE_KIND_ROLE)=="chat")
    item_a.setSelected(True);item_x.setSelected(True);group_b.setSelected(True)
    w._collection_selected(group_b)
    assert set(w.active_collection_ids)=={folder_a,folder_x}
    assert set(w.active_recipient_ids)=={-301,-302,-303}
    assert w.context_mode=="selection"
    w.close()

def test_stale_chat_history_cannot_replace_the_current_conversation(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui7.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.context_mode="chat";w.selected_peer=-402
    w.store.cache_messages([{"peer_id":-402,"message_id":1,"sender_id":1,"sender_name":"B","text":"Güncel sohbet","date":"2026-11-18T10:00:00","outgoing":0,"media_json":None}])
    w._render_messages(-402);w._render_messages(-401)
    assert w.messages.count()==1 and w.messages.item(0).data(main.Qt.UserRole)["peer_id"]==-402
    w.close()

def test_enter_key_sends_only_in_private_chat_mode():
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager.main import FileDropTextEdit
    edit=FileDropTextEdit();sent=[];edit.sendRequested.connect(lambda:sent.append(True))
    QTest.keyClick(edit,Qt.Key_Return)
    assert edit.toPlainText()=="\n" and sent==[]
    edit.clear();edit.send_on_enter=True;QTest.keyClick(edit,Qt.Key_Return)
    assert sent==[True] and edit.toPlainText()==""
    QTest.keyClick(edit,Qt.Key_Return,Qt.ShiftModifier)
    assert edit.toPlainText()=="\n" and sent==[True]

def test_bulk_confirmation_shows_full_recipient_collection_paths(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui8.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();peer=-501
    w.store.upsert_chats([{"peer_id":peer,"access_hash":1,"title":"YZ 1. Sınıf","kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None}])
    root=w.store.create_collection("İstanbul Rumeli Üniversitesi");dept=w.store.create_collection("Yapay Zekâ Bölümü",root);child=w.store.create_collection("YZ 1. Sınıf",dept);w.store.add_chats_to_collection(child,[peer])
    dlg=main.BulkConfirmDialog([{"peer_id":peer,"title":"YZ 1. Sınıf"}],w.store,"Ders duyurusu",["/tmp/duyuru.pdf"],w)
    assert dlg.targets_table.item(0,0).text()=="YZ 1. Sınıf"
    assert dlg.targets_table.item(0,1).text()=="İstanbul Rumeli Üniversitesi › Yapay Zekâ Bölümü › YZ 1. Sınıf"
    assert dlg.message_view.toPlainText()=="Ders duyurusu"
    labels=[label.text() for label in dlg.findChildren(main.QLabel)]
    assert any("duyuru.pdf" in label for label in labels)
    assert dlg.targets_table.horizontalScrollBarPolicy()==Qt.ScrollBarAsNeeded
    dlg.close();w.close()

def test_history_columns_are_sortable_resizable_and_include_message_and_files(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui9.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();folder=w.store.create_collection("Üniversite")
    target={"peer_id":-601,"title":"Akademik Grup","can_send":1};w.store.create_job("history-job",folder,"Toplantı duyurusu",["/tmp/toplanti.pdf"],[target]);w.refresh_history()
    assert w.history.columnCount()==7
    assert w.history.isSortingEnabled()
    assert w.history.horizontalHeader().sectionResizeMode(0)==main.QHeaderView.Interactive
    assert w.history.item(0,5).text()=="Toplantı duyurusu" and w.history.item(0,6).text()=="toplanti.pdf"
    w.close()

def test_chat_multi_selection_survives_refresh_and_suppresses_history(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui10.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();rows=[]
    for peer_id,title in ((-701,"Birinci sohbet"),(-702,"İkinci sohbet")):
        rows.append({"peer_id":peer_id,"access_hash":1,"title":title,"kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"Son mesaj","last_message_at":"2026-11-18"})
    w.store.upsert_chats(rows);w.refresh_chats();w.chat_list.blockSignals(True)
    first,second=w.chat_list.item(0),w.chat_list.item(1);first.setSelected(True);second.setSelected(True);w.chat_list.setCurrentItem(second,main.QItemSelectionModel.NoUpdate);w.chat_list.blockSignals(False)
    w._chat_selected()
    assert w.context_mode=="selection" and w.selected_peer is None and w.active_recipient_ids==[-701,-702]
    assert w.messages.count()==0
    w.refresh_chats()
    assert {int(item.data(main.Qt.UserRole)) for item in w.chat_list.selectedItems()}=={-701,-702}
    assert w.context_mode=="selection" and w.messages.count()==0
    w.close()

def test_chat_selection_context_menu_adds_folder_or_starts_bulk(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"ui11.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();rows=[]
    for peer_id,title in ((-711,"Birinci"),(-712,"İkinci")):
        rows.append({"peer_id":peer_id,"access_hash":1,"title":title,"kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None})
    w.store.upsert_chats(rows);folder=w.store.create_collection("Hedef klasör");w.refresh_chats();w.show();app.processEvents()
    first,second=w.chat_list.item(0),w.chat_list.item(1);w.chat_list.blockSignals(True);first.setSelected(True);second.setSelected(True);w.chat_list.setCurrentItem(second,main.QItemSelectionModel.NoUpdate);w.chat_list.blockSignals(False)
    w._chat_selected();captured={}
    monkeypatch.setattr(w,"_start_bulk",lambda **kwargs:captured.update(kwargs))
    class Action:
        def __init__(self,label):self.label=label
        def text(self):return self.label
    class FakeMenu:
        choice=""
        def __init__(self,*args):self.items=[]
        def addAction(self,label):action=Action(label);self.items.append(action);return action
        def exec(self,*args):return next(action for action in self.items if action.text()==self.choice)
    monkeypatch.setattr(main,"QMenu",FakeMenu)
    FakeMenu.choice="Seçililere toplu mesaj gönder"
    w._chat_menu(w.chat_list.visualItemRect(first).center())
    assert captured["direct_peer_ids"]==[-711,-712]
    assert w.context_mode=="selection" and w.messages.count()==0
    FakeMenu.choice="Seçilileri klasöre ekle"
    monkeypatch.setattr(main.QInputDialog,"getItem",lambda *args:("Hedef klasör",True))
    w._chat_menu(w.chat_list.visualItemRect(first).center())
    assert {row["peer_id"] for row in w.store.collection_chats(folder)}=={-711,-712}
    w.close()

def test_clipboard_image_paste_adds_a_real_attachment(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"app_data_dir",lambda:tmp_path)
    edit=main.FileDropTextEdit();received=[];edit.filesDropped.connect(received.extend)
    image=QImage(3,3,QImage.Format_ARGB32);image.fill(QColor("red"));app.clipboard().setImage(image)
    QTest.keyClick(edit,Qt.Key_V,Qt.ControlModifier)
    assert len(received)==1 and received[0].endswith(".png")
    assert __import__("pathlib").Path(received[0]).is_file()
    app.clipboard().clear()

def test_reply_selection_displays_a_clearable_quote_preview(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"reply.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w._set_reply({"message_id":42,"sender_name":"Ayşe Demir","text":"Yarınki toplantı saat kaçta?"})
    assert w.reply_to==42 and not w.reply_preview_frame.isHidden()
    assert "Ayşe Demir" in w.reply_preview.text() and "Yarınki toplantı" in w.reply_preview.text()
    w._clear_reply();assert w.reply_to is None and w.reply_preview_frame.isHidden()
    w.close()

def test_dismissing_message_context_menu_does_not_start_download(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"menu.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.messages.resize(500,300);item=main.QListWidgetItem();item.setData(main.Qt.UserRole,{"peer_id":-9701,"message_id":1,"sender_name":"Yusuf","text":"Test","outgoing":0,"media_json":None});w.messages.addItem(item);w.messages.show();app.processEvents()
    opened=[]
    class FakeMenu(main.QMenu):
        def exec(self,*args):
            opened.append(True)
            return None
    monkeypatch.setattr(main,"QMenu",FakeMenu)
    def fail_if_download(*args):raise AssertionError("menu dismissal must not start a download")
    monkeypatch.setattr(main.QFileDialog,"getSaveFileName",fail_if_download)
    w._message_menu(w.messages.visualItemRect(item).center(),item=item)
    assert opened==[True]
    w.close()

def test_chat_message_time_uses_local_timezone_and_displays_reactions():
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    value="2026-11-19T12:30:00+00:00"
    expected=main._local_datetime(value).strftime("%H:%M")
    assert main._format_local_datetime(value,"%H:%M")==expected
    row=main.MessageBubbleRow({"sender_name":"Yusuf","text":"Merhaba","date":value,"outgoing":1,"reactions_json":'[{"emoji":"👍","count":2}]',"reply_json":'{"sender":"Ayşe","text":"Toplantı saat kaçta?"}'})
    assert any(label.text()=="👍 2" for label in row.findChildren(main.QLabel))
    assert any("Ayşe" in label.text() and "Toplantı saat kaçta?" in label.text() for label in row.findChildren(main.QLabel))

def test_private_and_group_bubbles_follow_telegram_sender_and_receipt_rules():
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    private=main.MessageBubbleRow({"chat_kind":"Kişi","sender_name":"Yusuf Batur","text":"Merhaba","date":"2026-11-25T10:30:00+00:00","outgoing":0})
    group=main.MessageBubbleRow({"chat_kind":"Grup","sender_name":"Ayşe Yılmaz","text":"Duyuru","date":"2026-11-25T10:31:00+00:00","outgoing":0})
    private_avatar=main.MessageBubbleRow({"chat_kind":"Kişi","sender_name":"Yusuf Batur","text":"Merhaba","date":"2026-11-25T10:30:00+00:00","outgoing":0,"show_sender_avatar":True})
    sent=main.MessageBubbleRow({"chat_kind":"Kişi","sender_name":"Siz","text":"Gönderildi","date":"2026-11-25T10:32:00+00:00","outgoing":1,"read":False})
    read=main.MessageBubbleRow({"chat_kind":"Kişi","sender_name":"Siz","text":"Okundu","date":"2026-11-25T10:33:00+00:00","outgoing":1,"read":True})
    assert private.sender.isHidden() and hasattr(private,"sender_avatar")
    assert not group.sender.isHidden() and group.sender.text()=="Ayşe Yılmaz" and hasattr(group,"sender_avatar")
    assert private_avatar.sender.isHidden() and hasattr(private_avatar,"sender_avatar")
    assert sent.ticks.text()=="✓" and read.ticks.text()=="✓✓"

def test_image_preview_opens_fullscreen_without_automatically_downloading(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"image-preview.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();request={"peer_id":-17,"message_id":21,"media_json":'{"name":"foto.jpg","size":2048,"mime_type":"image/jpeg"}'}
    item=main.QListWidgetItem();w.messages.addItem(item);w._set_message_bubble(item,{**request,"text":"","outgoing":0,"chat_kind":"Kişi"})
    preview=w.messages.itemWidget(item).findChild(main.QLabel,"imagePreview")
    image=QImage(32,24,QImage.Format_ARGB32);image.fill(QColor("#4477aa"));pixmap=main.QPixmap.fromImage(image);preview.setPixmap(pixmap);preview.setText("")
    opened=[]
    def capture_preview(dialog):
        opened.append((dialog.original,dialog.request,dialog.parent()))
        return main.QDialog.Rejected
    # The actual dialog is exercised by its separate widget tests; this captures
    # the preview click path and proves that only its explicit download action
    # can emit a download request.
    monkeypatch.setattr(main.FullScreenImageDialog,"exec",capture_preview)
    downloads=[];w._download_message=lambda target:downloads.append(target)
    preview.clicked.emit()
    assert opened and opened[0][1]["peer_id"]==request["peer_id"] and opened[0][1]["message_id"]==request["message_id"] and downloads==[]
    w.close()

def test_folder_rename_uses_clicked_folder_even_with_other_rows_selected(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"folder-rename.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();first=w.store.create_collection("Üniversite");second=w.store.create_collection("Yapay Zekâ");w.refresh_tree()
    item=w._tree_items[first];w.tree.blockSignals(True);item.setSelected(True);w._tree_items[second].setSelected(True);w.tree.blockSignals(False)
    monkeypatch.setattr(w.tree,"itemAt",lambda _pos:item)
    monkeypatch.setattr(main.QInputDialog,"getText",lambda *args,**kwargs:("Akademik",True))
    class FakeMenu:
        def __init__(self,*args):self.actions=[]
        def addAction(self,*args):
            action=object();self.actions.append((args[-1],action));return action
        def addSeparator(self):pass
        def exec(self,*args):return next(action for label,action in self.actions if label=="Yeniden adlandır")
    monkeypatch.setattr(main,"QMenu",FakeMenu)
    w._collection_menu(QPoint(0,0))
    assert next(row["name"] for row in w.store.collections() if row["id"]==first)=="Akademik"
    assert w.tree.currentItem().data(0,main.Qt.UserRole)==first
    w.close()

def test_folder_emoji_picker_contains_a_broad_catalog():
    from academic_chat_manager import main
    assert len(main.COLLECTION_ICON_OPTIONS)>500
    assert all(icon in main.COLLECTION_ICON_OPTIONS for icon in ("📚","🎓","🧪","🏫","🧠","❤️","🐈","🚀"))

@pytest.mark.asyncio
async def test_loading_group_sender_avatar_updates_bubble_without_rebuilding_message_list(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"avatar-refresh.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.selected_peer=-42;w.context_mode="chat"
    w.store.upsert_chats([{"peer_id":-42,"access_hash":None,"title":"Grup","kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None}])
    fallback=w._avatar_icon("Ayşe");w._append_message_bubble({"peer_id":-42,"message_id":5,"sender_id":73,"sender_name":"Ayşe","text":"Merhaba","outgoing":0,"chat_kind":"Grup","show_sender_avatar":True,"sender_avatar_icon":fallback})
    row=w.messages.itemWidget(w.messages.item(0));original_pixmap=row.sender_avatar.pixmap()
    image=QImage(24,16,QImage.Format_ARGB32);image.fill(QColor("#4477aa"));buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,"PNG")
    service=SimpleNamespace(client=SimpleNamespace(is_connected=lambda:True),download_profile_photo=lambda _peer: asyncio.sleep(0,result=bytes(buffer.data())))
    w.telegram=service;redraws=[];monkeypatch.setattr(w,"_render_messages",lambda peer:redraws.append(peer))
    await w._ensure_chat_avatar(73)
    updated=row.sender_avatar.pixmap()
    assert redraws==[] and w.messages.count()==1
    assert not updated.isNull() and updated.cacheKey()!=original_pixmap.cacheKey()
    w.telegram=None;w.close()

@pytest.mark.asyncio
async def test_preview_load_survives_message_widget_replacement_without_duplicate_requests(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"preview-race.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.show();request={"peer_id":-17,"message_id":21,"media_json":'{"name":"foto.jpg","size":2048,"mime_type":"image/jpeg"}'}
    image=QImage(32,24,QImage.Format_ARGB32);image.fill(QColor("#4477aa"));buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,"PNG");png=bytes(buffer.data())
    class Service:
        def __init__(self):self.calls=0;self.client=SimpleNamespace(is_connected=lambda:True)
        async def download_media_bytes(self,peer_id,message_id):
            self.calls+=1;await asyncio.sleep(.02);return png
    service=Service();w.telegram=service
    def add_preview(target=request):
        item=main.QListWidgetItem();w.messages.addItem(item)
        w._set_message_bubble(item,{**target,"text":"","outgoing":0,"chat_kind":"Kişi"})
        return w.messages.itemWidget(item).findChild(main.QLabel,"imagePreview")
    first=add_preview();w._queue_image_preview(request);task=w._image_preview_tasks[(request["peer_id"],request["message_id"])]
    w.messages.clear();app.processEvents();second=add_preview();w._queue_image_preview(request)
    assert w._image_preview_tasks[(request["peer_id"],request["message_id"])] is task
    await task;await asyncio.sleep(0)
    assert service.calls==1 and second.property("mediaLoaded") is True and not second.pixmap().isNull()
    missing={**request,"message_id":22}
    async def missing_media(_peer,_message):raise FileNotFoundError("Telegram mesajı bulunamadı")
    service.download_media_bytes=missing_media;missing_preview=add_preview(missing)
    await w._load_image_preview(missing)
    assert missing_preview.text()=="Önizleme yüklenemedi · aşağıdaki düğmeden indirebilirsiniz"
    w.telegram=None;w.close()

def test_clear_attachments_button_preserves_message_and_source_files(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"attachments.sqlite3"))
    monkeypatch.setattr(main,"app_data_dir",lambda:tmp_path)
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        button=w.clear_attachments
        assert button.objectName()=="clearAttachments"
        assert not button.isEnabled()
        assert button.accessibleName()=="Tüm ekleri kaldır"
        assert button.toolTip()
        source=tmp_path/"notes.txt"
        source.write_text("test",encoding="utf-8")
        w.message_input.setPlainText("Mesaj metni")
        w._add_chat_files([str(source)])
        assert button.isEnabled()
        assert "notes.txt" in w.pending_files_label.text()
        for theme in ("Koyu","Açık"):
            w.theme.setCurrentText(theme)
            assert "QPushButton#clearAttachments:disabled" in w.styleSheet()
        button.click()
        assert not button.isEnabled()
        assert w.pending_chat_files==[]
        assert w.pending_files_label.text()==""
        assert w.message_input.toPlainText()=="Mesaj metni"
        assert source.is_file()
    finally:
        w.close()

def test_application_icons_scale_and_follow_theme(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"icons.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        w.theme.setCurrentText("Açık")
        w.font_size.setValue(10)
        button=w.nav["chats"]
        assert button.text()=="Sohbetler" and not button.icon().isNull()
        assert not w.emoji_button.icon().isNull() and w.emoji_button.accessibleName()=="Emoji ekle"
        assert not w.tabs.tabIcon(0).isNull()
        assert not w.clear_attachments.icon().isNull()
        small=button.iconSize().width()
        w.font_size.setValue(20)
        assert button.iconSize().width()>small
        assert w.emoji_button.iconSize()==button.iconSize()==w.tabs.iconSize()
        # Use an inactive icon: the active accent foreground is shared by both themes.
        light=w.nav["settings"].icon().cacheKey()
        w.theme.setCurrentText("Koyu")
        assert w.nav["settings"].icon().cacheKey()!=light
        assert w.font_size.value()==20
        active=w.nav["settings"].icon().cacheKey()
        w.navigate("settings")
        assert w.nav["settings"].property("active")
        assert w.nav["settings"].icon().cacheKey()!=active
        w.font_size.setValue(13)
        default=w.store.create_collection("Standart")
        custom=w.store.create_collection("Özel",icon="⭐")
        w.refresh_tree()
        assert not w._tree_items[default].icon(0).isNull()
        assert w._tree_items[custom].text(0).startswith("⭐")
    finally:
        w.font_size.setValue(13)
        w.close()

def test_message_context_menu_is_shared_by_bubble_children_and_list(tmp_path,monkeypatch):
    from academic_chat_manager import main
    from PySide6.QtGui import QContextMenuEvent
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"unified-menu.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        message={"peer_id":-9701,"message_id":1,"sender_name":"Yusuf","text":"Test mesajı","date":"2026-11-19T12:30:00+00:00","outgoing":1,"media_json":'{"name":"test.txt"}',"reply_json":'{"sender":"Ayşe","text":"Önceki mesaj"}',"reactions_json":'[{"emoji":"👍","count":2}]'}
        w._append_message_bubble(message)
        item=w.messages.item(0)
        row=w.messages.itemWidget(item)
        w.show()
        app.processEvents()
        menus=[]
        choose_text=None
        class CaptureMenu(main.QMenu):
            def exec(self,*args):
                actions=[action for action in self.actions() if not action.isSeparator()]
                menus.append([action.text() for action in actions])
                assert all(not action.icon().isNull() for action in actions)
                return next((action for action in actions if action.text()==choose_text),None)
        monkeypatch.setattr(main,"QMenu",CaptureMenu)
        expected=["Yanıtla","Metni kopyala","Tepki bırak","Dosyayı indir…","Mesajı düzenle","Mesajı sil"]
        def context_click(widget):
            pos=widget.rect().center()
            event=QContextMenuEvent(QContextMenuEvent.Reason.Mouse,pos,widget.mapToGlobal(pos))
            QApplication.sendEvent(widget,event)
        for widget in (row,row.bubble,row.body,row.sender,row.footer,row.reply_quote,row.reactions_label):
            context_click(widget)
        w.messages.customContextMenuRequested.emit(w.messages.visualItemRect(item).center())
        assert menus==[expected]*8
        row.body.setSelection(0,4)
        choose_text="Seçili metni kopyala"
        context_click(row.body)
        assert "Seçili metni kopyala" in menus[-1]
        assert app.clipboard().text()=="Test"
        choose_text="Metni kopyala"
        context_click(row.bubble)
        assert app.clipboard().text()=="Test mesajı"
        # Incoming text-only messages must not expose outgoing/media operations.
        w._append_message_bubble({**message,"message_id":2,"outgoing":0,"media_json":None})
        incoming=w.messages.itemWidget(w.messages.item(1))
        choose_text=None
        context_click(incoming.body)
        assert menus[-1]==["Yanıtla","Metni kopyala","Tepki bırak"]
    finally:
        app.clipboard().clear()
        w.close()

def test_attachment_cards_show_metadata_and_emit_download_reference():
    from academic_chat_manager import main
    import json
    app=QApplication.instance() or QApplication([])
    row=main.MessageBubbleRow({"peer_id":-17,"message_id":21,"text":"","outgoing":0,"media_json":'{"name":"ders.pdf","size":2048,"mime_type":"application/pdf"}'})
    captured=[]
    row.downloadRequested.connect(captured.append)
    assert any(label.text()=="ders.pdf" for label in row.findChildren(main.QLabel))
    assert any("2.0 KB" in label.text() for label in row.findChildren(main.QLabel))
    assert len(row.attachment_buttons)==1 and row.attachment_buttons[0].isEnabled()
    row.attachment_buttons[0].click()
    assert captured[0]["peer_id"]==-17 and captured[0]["message_id"]==21
    assert json.loads(captured[0]["media_json"])["name"]=="ders.pdf"

def test_image_attachment_has_preview_area():
    from academic_chat_manager.main import MessageBubbleRow
    row=MessageBubbleRow({"peer_id":-17,"message_id":21,"text":"","outgoing":0,"media_json":'{"name":"foto.jpg","size":2048,"mime_type":"image/jpeg"}'})
    preview=row.findChild(__import__('PySide6.QtWidgets',fromlist=['QLabel']).QLabel,"imagePreview")
    assert preview is not None and preview.property("mediaRequest")["message_id"]==21

def test_profile_photo_avatar_is_cropped_into_icon():
    from academic_chat_manager.main import MainWindow
    app=QApplication.instance() or QApplication([])
    image=QImage(24,16,QImage.Format_ARGB32);image.fill(QColor("#4477aa"));buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,"PNG")
    icon=MainWindow._photo_avatar_icon(None,bytes(buffer.data()))
    assert icon is not None and not icon.isNull() and not icon.pixmap(42,42).isNull()

def test_invite_copy_text_excludes_errors_and_keeps_folder_indentation():
    from academic_chat_manager.main import InviteLinksDialog
    value=InviteLinksDialog._format_entries([
        {"path":["Akademik","Bilgisayar"],"link":"https://t.me/+ok"},
        {"path":["Akademik","YZ Laboratuvarı"],"link":"https://t.me/+ok2"},
        {"path":["Akademik","Kişi"],"error":"Kişi sohbetleri desteklenmiyor"},
    ])
    assert "https://t.me/+ok" in value
    assert "desteklenmiyor" not in value
    assert "├──" in value and "└──" in value

def test_dismissing_folder_context_menu_does_not_create_subfolder(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"context-dismiss.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();folder=w.store.create_collection("Üniversite");w.refresh_tree();item=w._tree_items[folder]
    monkeypatch.setattr(w.tree,"itemAt",lambda _pos:item)
    class DismissedMenu:
        def __init__(self,*_args):pass
        def addAction(self,*_args):return object()
        def addSeparator(self):pass
        def exec(self,*_args):return None
    monkeypatch.setattr(main,"QMenu",DismissedMenu)
    before=len(w.store.collections());w._collection_menu(QPoint(0,0))
    assert len(w.store.collections())==before
    w.close()

def test_folder_sidebar_can_be_hidden_and_restored(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    from academic_chat_manager import main
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"sidebar.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow();w.show();app.processEvents();w.toggle_sidebar()
    assert not w.sidebar.isVisible() and w.store.preference("appearance/sidebar_visible") is False
    w.toggle_sidebar()
    assert w.sidebar.isVisible() and w.store.preference("appearance/sidebar_visible") is True
    w.close()


def test_bulk_history_can_download_each_sent_attachment(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"media-history.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        folder=w.store.create_collection("Dosyalar")
        w.store.create_job("files",folder,"Duyuru",["missing-a.pdf","missing-b.txt"],[{"peer_id":-17,"title":"Grup"}])
        records=[{"index":0,"name":"missing-a.pdf","size":2048,"message_id":21},{"index":1,"name":"missing-b.txt","size":1024,"message_id":29}]
        w.store.update_target("files",-17,"sent",message_id=29,attachments=records)
        w.refresh_history()
        assert w.history_download_btn.isEnabled()
        assert [card["message_id"] for card in w._history_downloadable("files")]==[21,29]
        w.active_collection_ids=[folder]
        w._render_collection_history()
        row=w.messages.itemWidget(w.messages.item(0))
        assert len(row.attachment_buttons)==2 and all(button.isEnabled() for button in row.attachment_buttons)
    finally:
        w.close()

def test_reaction_menu_marks_own_reactions_and_updates_exact_row(tmp_path,monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"reaction-ui.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        original={"peer_id":-17,"message_id":2,"sender_id":1,"sender_name":"Yusuf","text":"Mesaj","date":"2026-11-19T12:00:00+00:00","outgoing":0,"media_json":None,"reactions_json":json.dumps([{"emoji":"❤","count":2,"chosen":True},{"emoji":"👍","count":3,"chosen":False}])}
        other={**original,"message_id":3}
        w.store.cache_messages([original,other])
        w._append_message_bubble(original)
        w._append_message_bubble(other)
        first=w.messages.item(0)
        row=w.messages.itemWidget(first)
        class CaptureMenu(main.QMenu):
            def exec(self,*args):
                submenu=next(action.menu() for action in self.actions() if action.text()=="Tepki bırak")
                selected=[action.text() for action in submenu.actions() if action.isChecked()]
                assert selected==["❤️"]
                return None
        monkeypatch.setattr(main,"QMenu",CaptureMenu)
        w._message_menu(w.messages.visualItemRect(first).center(),item=first)
        async def react(peer,message_id,emoji):
            assert (peer,message_id,emoji)==(-17,2,"❤️")
            return "removed",[{"emoji":"❤","count":1,"chosen":False}]
        w.telegram=SimpleNamespace(client=SimpleNamespace(is_connected=lambda:True),send_reaction=react)
        asyncio.run(w._react_to_message(original,"❤️"))
        assert w.messages.count()==2 and w.messages.itemWidget(first) is row
        assert row.reactions_label.text()=="❤ 1"
        assert json.loads(first.data(Qt.UserRole)["reactions_json"])[0]["chosen"] is False
        assert json.loads(w.store.messages(-17)[0]["reactions_json"])[0]["chosen"] is False
        assert json.loads(w.messages.item(1).data(Qt.UserRole)["reactions_json"])[0]["chosen"] is True
    finally:
        w.telegram=None
        w.close()

def test_edited_indicator_and_live_update_preserve_message_state(tmp_path,monkeypatch):
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"edits-ui.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    try:
        original={"peer_id":-17,"message_id":2,"sender_id":1,"sender_name":"Yusuf","text":"İlk metin","date":"2026-11-19T12:00:00+00:00","outgoing":0,"media_json":None,"reactions_json":'[{"emoji":"👍","count":1}]',"reply_json":'{"sender":"Ayşe","text":"Merhaba"}'}
        w.selected_peer=-17;w.context_mode="chat"
        w.store.cache_messages([original])
        w._append_message_bubble(original)
        item=w.messages.item(0)
        initial=w.messages.itemWidget(item).footer.text()
        assert "düzenlendi" not in initial
        monkeypatch.setattr(w,"_show_local_notification",lambda *args:__import__("pytest").fail("edit must not notify"))
        edit={"peer_id":-17,"message_id":2,"text":"Yeni metin","media_json":None,"edit_date":"2026-11-19T12:05:00+00:00","edit_hidden":0}
        w._on_message_edited(edit)
        row=w.messages.itemWidget(item)
        assert row.body.text()=="Yeni metin"
        assert row.footer.text()=="düzenlendi · "+initial
        assert "Düzenlenme zamanı" in row.footer.toolTip()
        assert row.reactions_label.text()=="👍 1"
        assert "Merhaba" in row.reply_quote.text()
        assert w.messages.count()==1
        w._on_message_edited({**edit,"text":"Eski","edit_date":"2026-11-19T12:04:00+00:00"})
        assert w.messages.itemWidget(item).body.text()=="Yeni metin"
        w._on_message_edited({**edit,"edit_date":"2026-11-19T12:06:00+00:00","edit_hidden":1})
        assert w.messages.itemWidget(item).footer.text()==initial
    finally:
        w.close()

def test_invite_batch_reports_partial_success_and_stops_on_flood_wait(tmp_path,monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from telethon import errors
    from academic_chat_manager import main
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(main,"Store",lambda:__import__('academic_chat_manager.storage',fromlist=['Store']).Store(tmp_path/"invites-ui.sqlite3"))
    main.PREFS.setValue("onboarding/dismissed",True)
    w=MainWindow()
    calls=[];captured=[]
    async def export(peer_id,access_hash=None):
        calls.append((peer_id,access_hash))
        if peer_id==-2:raise errors.ChatAdminRequiredError(None)
        if peer_id==-3:raise errors.FloodWaitError(None,12)
        return "https://t.me/+example_invite"
    class Dialog:
        def __init__(self,entries,parent):captured.extend(entries)
        def exec(self):return 0
    monkeypatch.setattr(main,"InviteLinksDialog",Dialog)
    w.telegram=SimpleNamespace(client=SimpleNamespace(is_connected=lambda:True),export_chat_invite_link=export)
    targets={
        -1:{"paths":[["A","Grup"],["B","Grup"],["A","Grup"]],"access_hash":123},
        -2:{"paths":[["A","Yetkisiz"]]},
        -3:{"paths":[["A","Bekle"]]},
        -4:{"paths":[["A","Sonraki"]]},
        7:{"paths":[["A","Kişi"]]},
    }
    try:
        asyncio.run(w._create_invite_links(targets))
        assert calls==[(-1,123),(-2,None),(-3,None)]
        assert len(captured)==6
        assert captured[0]["link"]==captured[1]["link"]=="https://t.me/+example_invite"
        assert "yönetici" in captured[2]["error"]
        assert "12 saniye" in captured[3]["error"] and captured[3]["error"]==captured[4]["error"]
        assert "Kişi" in captured[5]["error"]
        assert "1/5 başarılı" in w.statusBar().currentMessage()
    finally:
        w.telegram=None
        w.close()
