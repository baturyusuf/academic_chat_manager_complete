import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
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
