from academic_chat_manager.storage import Store
import pytest

@pytest.fixture
def store(tmp_path):return Store(tmp_path/"db.sqlite3")
def add_chat(s,pid,title="Group"):
    s.upsert_chats([{"peer_id":pid,"access_hash":pid+100,"title":title,"kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None}])
def test_hierarchy_and_descendant_deduplication(store):
    add_chat(store,-1001);add_chat(store,-1002)
    root=store.create_collection("Üniversite");dept=store.create_collection("YZ",root);one=store.create_collection("1. Sınıf",dept);two=store.create_collection("2. Sınıf",dept)
    store.add_chats_to_collection(one,[-1001]);store.add_chats_to_collection(two,[-1001,-1002])
    assert {r['peer_id'] for r in store.collection_chats(root)}=={-1001,-1002}
    with pytest.raises(ValueError):store.move_collection(root,one)
def test_delete_collection_does_not_delete_telegram_chat(store):
    add_chat(store,-2001,"YZ Sınıfı");cid=store.create_collection("Akademik");store.add_chats_to_collection(cid,[-2001]);store.delete_collection(cid)
    assert store.chat(-2001)['title']=="YZ Sınıfı"
def test_hidden_chats_are_filterable(store):
    add_chat(store,-3001);store.set_hidden([-3001],True)
    assert store.chats()==[]
    assert store.chats(include_hidden=True)[0]['hidden']==1
def test_collection_chat_removal_keeps_chat(store):
    add_chat(store,-4001);cid=store.create_collection("Lab");store.add_chats_to_collection(cid,[-4001]);store.remove_chat_from_collection(cid,-4001)
    assert store.collection_chats(cid)==[] and store.chat(-4001)
def test_collection_cycle_is_rejected(store):
    a=store.create_collection("A");b=store.create_collection("B",a);c=store.create_collection("C",b)
    with pytest.raises(ValueError):store.move_collection(a,c)
def test_full_sync_marks_missing_peers_unavailable_without_losing_folder_membership(store):
    add_chat(store,-5001,"Old room");folder=store.create_collection("Academics");store.add_chats_to_collection(folder,[-5001])
    store.upsert_chats([{"peer_id":-5002,"access_hash":1,"title":"New room","kind":"Grup","username":None,"can_send":1,"unread_count":0,"last_message":"","last_message_at":None}],complete_sync=True)
    assert store.chat(-5001)['available']==0
    assert store.collection_chats(folder)==[]
    assert store.chat(-5001) is not None

def test_last_message_receipt_state_is_persisted_and_legacy_rows_default_cleanly(store):
    add_chat(store,-5003,"Outgoing")
    store.update_last_message(-5003,"Sent", "2026-11-25T10:00:00+00:00", outgoing=True, read=False, message_id=44)
    assert store.chat(-5003)["last_message_outgoing"]==1
    assert store.chat(-5003)["last_message_read"]==0
    assert store.chat(-5003)["last_message_id"]==44
    assert store.mark_last_message_read(-5003,44)
    assert store.chat(-5003)["last_message_read"]==1
    add_chat(store,-5004,"Incoming")
    assert store.chat(-5004)["last_message_outgoing"]==0
    assert store.chat(-5004)["last_message_read"]==0

def test_chat_upsert_migrates_legacy_last_message_receipt_columns(tmp_path):
    path=tmp_path/"legacy-chat-receipt.sqlite3";store=Store(path)
    with store.db() as db:db.execute("ALTER TABLE chats DROP COLUMN last_message_id")
    reopened=Store(path)
    add_chat(reopened,-5005,"Legacy")
    assert reopened.chat(-5005)["last_message_id"] is None
def test_preferences_persist_between_store_instances(tmp_path):
    path=tmp_path/"prefs.sqlite";Store(path).set_preference("appearance/font_size",16)
    assert Store(path).preference("appearance/font_size")==16

def test_open_skips_legacy_send_jobs_whose_collection_was_deleted(tmp_path):
    path=tmp_path/"legacy.sqlite";store=Store(path);folder=store.create_collection("Daha sonra silinen klasör")
    store.create_job("legacy-job",folder,"Eski duyuru",[],[{"peer_id":-9501,"title":"Grup"}])
    store.delete_collection(folder)
    reopened=Store(path)
    assert reopened.jobs()[0]["id"]=="legacy-job"
    assert reopened.job_collection_ids("legacy-job")==[]

def test_cached_message_reactions_survive_storage_roundtrip(store):
    store.cache_messages([{"peer_id":-9601,"message_id":1,"sender_id":1,"sender_name":"Yusuf","text":"Merhaba","date":"2026-11-19T10:00:00+00:00","outgoing":1,"media_json":None,"reactions_json":'[{"emoji":"👍","count":2,"chosen":true}]',"reply_json":'{"sender":"Ayşe","text":"Yarın görüşürüz"}'}])
    assert store.messages(-9601)[0]["reactions_json"]=='[{"emoji":"👍","count":2,"chosen":true}]'
    assert store.messages(-9601)[0]["reply_json"]=='{"sender":"Ayşe","text":"Yarın görüşürüz"}'
def test_messages_are_returned_oldest_to_newest_and_can_be_paginated(store):
    def message(message_id):
        return {"peer_id":-123,"message_id":message_id,"sender_id":1,"sender_name":"Yusuf","text":str(message_id),"date":"2026-01-01T10:00:00","outgoing":0,"media_json":None}
    store.cache_messages([message(i) for i in (1,2,3,4)])

    assert [row["message_id"] for row in store.messages(-123,2)]==[3,4]
    assert [row["message_id"] for row in store.messages(-123,2,before_id=4)]==[2,3]
def test_collection_reorder_changes_sibling_order(store):
    first=store.create_collection("Birinci");second=store.create_collection("İkinci")
    assert store.reorder_collection(second,-1)
    assert [c['name'] for c in store.collections()]==["İkinci","Birinci"]

def test_collection_message_history_is_exactly_scoped_and_supports_multi_folder_jobs(store):
    root=store.create_collection("Üniversite");child=store.create_collection("Bölüm",root);other=store.create_collection("Diğer")
    target={"peer_id":-9001,"title":"Grup","can_send":1}
    store.create_job("root-job",root,"Ana klasör duyurusu",[],[target])
    store.create_job("child-job",child,"Alt klasör duyurusu",[],[target])
    store.create_job("multi-job",root,"Birden fazla klasör duyurusu",[],[target],collection_ids=[root,other])

    assert {row["id"] for row in store.collection_messages([root])}=={"root-job","multi-job"}
    assert [row["id"] for row in store.collection_messages([child])]==["child-job"]
    assert {row["id"] for row in store.collection_messages([root,other])}=={"root-job","multi-job"}
    assert store.job_collection_ids("multi-job")==[root,other]

def test_manual_cancellation_marks_pending_targets_and_preserves_sent_targets(store):
    add_chat(store,-9010,"Bekleyen");add_chat(store,-9011,"Gönderildi")
    folder=store.create_collection("Üniversite");dept=store.create_collection("Bilgisayar Mühendisliği",folder);child=store.create_collection("YZ Laboratuvarı",dept)
    store.add_chats_to_collection(child,[-9010,-9011])
    targets=[{"peer_id":-9010,"title":"Bekleyen"},{"peer_id":-9011,"title":"Gönderildi"}]
    store.create_job("cancel-target",folder,"Duyuru",["/tmp/ek.pdf"],targets)
    store.update_target("cancel-target",-9011,"sent")
    assert store.chat_collection_paths(-9010)==["Üniversite › Bilgisayar Mühendisliği › YZ Laboratuvarı"]
    assert store.cancel_target("cancel-target",-9010)
    assert [r["status"] for r in store.job_targets("cancel-target")]==["cancelled","sent"]
    store.create_job("cancel-job",folder,"Duyuru",[],targets)
    assert store.cancel_job("cancel-job")
    assert all(r["status"]=="cancelled" for r in store.job_targets("cancel-job"))

def test_attachment_references_survive_legacy_schema_migration(tmp_path):
    import json
    path=tmp_path/"legacy-attachments.sqlite"
    store=Store(path)
    with store.db() as db:
        db.execute("ALTER TABLE send_targets DROP COLUMN attachments_json")
    reopened=Store(path)
    reopened.create_job("files",None,"",["a.pdf","b.txt"],[{"peer_id":-71,"title":"Grup"}])
    records=[{"index":0,"name":"a.pdf","size":123,"message_id":21},{"index":1,"name":"b.txt","size":456,"message_id":29}]
    reopened.update_target("files",-71,"sent",message_id=29,attachments=records)
    target=Store(path).job_targets("files")[0]
    assert target["telegram_message_id"]==29
    assert json.loads(target["attachments_json"])==records

def test_edit_metadata_migration_and_stale_history_protection(tmp_path):
    path=tmp_path/"legacy-edit.sqlite"
    store=Store(path)
    with store.db() as db:
        db.execute("ALTER TABLE cached_messages DROP COLUMN edit_hidden")
        db.execute("ALTER TABLE cached_messages DROP COLUMN edit_date")
    store=Store(path)
    original={"peer_id":-31,"message_id":5,"sender_id":1,"sender_name":"Yusuf","text":"İlk metin","date":"2026-11-19T12:00:00+00:00","outgoing":0,"media_json":None,"reactions_json":'[{"emoji":"👍","count":1}]',"reply_json":'{"sender":"Ayşe","text":"Merhaba"}'}
    store.cache_messages([original])
    edit={"peer_id":-31,"message_id":5,"text":"Düzeltilmiş metin","media_json":None,"edit_date":"2026-11-19T12:05:00+00:00","edit_hidden":0}
    assert store.update_message_edit(edit)
    assert not store.update_message_edit({**edit,"text":"Eski düzenleme","edit_date":"2026-11-19T12:04:00+00:00"})
    store.cache_messages([original])
    row=Store(path).messages(-31)[0]
    assert row["text"]=="Düzeltilmiş metin" and row["edit_date"]==edit["edit_date"]
    assert row["reactions_json"]==original["reactions_json"] and row["reply_json"]==original["reply_json"]
    assert store.update_message_edit({**edit,"edit_date":"2026-11-19T12:06:00+00:00","edit_hidden":1})
    assert store.messages(-31)[0]["edit_hidden"]==1
