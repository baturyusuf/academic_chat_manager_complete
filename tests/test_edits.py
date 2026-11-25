from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from telethon import events, types

from academic_chat_manager.telegram_service import TelegramService, edit_metadata


def test_edit_metadata_uses_server_timestamp_and_hide_flag():
    stamp=datetime(2026,11,19,12,5,tzinfo=timezone.utc)
    assert edit_metadata(SimpleNamespace(edit_date=stamp,edit_hide=True))=={"edit_date":stamp.isoformat(),"edit_hidden":1}
    assert edit_metadata(SimpleNamespace())=={"edit_date":None,"edit_hidden":0}


@pytest.mark.asyncio
async def test_history_and_live_edits_receive_server_metadata(tmp_path):
    stamp=datetime(2026,11,19,12,5,tzinfo=timezone.utc)
    message=SimpleNamespace(id=42,peer_id=types.PeerUser(7),sender_id=7,sender=None,out=False,message="Yeni metin",date=stamp,edit_date=stamp,edit_hide=False,media=None,reactions=None,reply_to=None)
    class Client:
        def __init__(self):self.handlers=[]
        async def get_messages(self,*args,**kwargs):return [message]
        def add_event_handler(self,handler,event):self.handlers.append((handler,event))
    service=TelegramService(tmp_path/"session")
    service.client=Client()
    rows=await service.history(7)
    assert rows[0]["edit_date"]==stamp.isoformat() and rows[0]["edit_hidden"]==0
    arrivals=[];edits=[]
    service.start_updates(arrivals.append,edits.append)
    handler=next(handler for handler,event in service.client.handlers if isinstance(event,events.MessageEdited))
    await handler(SimpleNamespace(message=message))
    assert not arrivals
    assert edits==[{"peer_id":7,"message_id":42,"text":"Yeni metin","media_json":None,"edit_date":stamp.isoformat(),"edit_hidden":0}]

@pytest.mark.asyncio
async def test_outgoing_read_updates_are_exposed_as_per_message_receipts(tmp_path):
    class Client:
        def __init__(self):self.handlers=[]
        def add_event_handler(self,handler,event):self.handlers.append((handler,event))
    service=TelegramService(tmp_path/"session-read")
    service.client=Client();read_updates=[]
    service.start_updates(lambda row:None,read_handler=lambda peer_id,max_id:read_updates.append((peer_id,max_id)))
    handler=next(handler for handler,event in service.client.handlers if isinstance(event,events.MessageRead))
    peer=types.PeerUser(7)
    await handler(SimpleNamespace(outbox=False,peer=peer,max_id=49))
    assert read_updates==[] and not service.is_message_read(7,49)
    await handler(SimpleNamespace(outbox=True,peer=peer,max_id=49))
    assert read_updates==[(7,49)] and service.is_message_read(7,49) and not service.is_message_read(7,50)

def test_live_update_handlers_are_registered_only_once(tmp_path):
    class Client:
        def __init__(self):self.handlers=[]
        def add_event_handler(self,handler,event):self.handlers.append((handler,event))
    service=TelegramService(tmp_path/"session-once")
    service.client=Client()
    service.start_updates(lambda row:None,lambda row:None,lambda peer_id,max_id:None)
    first_handlers=list(service.client.handlers)
    service.start_updates(lambda row:None,lambda row:None,lambda peer_id,max_id:None)
    assert len(service.client.handlers)==3
    assert service.client.handlers==first_handlers
