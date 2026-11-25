import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
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
    class FakeMenu:
        def __init__(self,*args):pass
        def addAction(self,*args):return object()
        def addMenu(self,*args):return FakeMenu()
        def exec(self,*args):return None
    monkeypatch.setattr(main,"QMenu",FakeMenu)
    def fail_if_download(*args):raise AssertionError("menu dismissal must not start a download")
    monkeypatch.setattr(main.QFileDialog,"getSaveFileName",fail_if_download)
    w._message_menu(QPoint(10,10))
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
