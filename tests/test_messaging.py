import asyncio
from types import SimpleNamespace
import pytest
from telethon import errors
from academic_chat_manager.messaging import BulkSender

class StoreFake:
    def __init__(self):self.states={};self.attachments={}
    def collection_chats(self,*a,**k):return []
    def create_job(self,j,c,m,f,targets):self.states[j]={t['peer_id']:"pending" for t in targets}
    def update_target(self,j,p,status,error=None,message_id=None,attachments=None):
        self.states[j][p]=status
        if attachments is not None:self.attachments[(j,p)]=attachments
    def finish_job(self,j,status="finished"):self.finished=status
class TelegramFake:
    def __init__(self,sender=None,flood=False):self.sent=[];self.sender=sender;self.flood=flood
    async def send_text(self,p,text):
        self.sent.append((p,text))
        if self.sender:self.sender.cancel()
        if self.flood and p==2:raise errors.FloodWaitError(None,3)
        return SimpleNamespace(id=10)
    async def send_files(self,p,files,caption=""):self.sent.append((p,caption,tuple(files)));return [SimpleNamespace(id=11)]
@pytest.mark.asyncio
async def test_bulk_send_sends_once_to_each_distinct_target():
    s=StoreFake();t=TelegramFake();sender=BulkSender(s,t);targets=[{"peer_id":1,"title":"A","can_send":1},{"peer_id":2,"title":"B","can_send":1}]
    job=sender.prepare_job(1,"Notice",[],targets);await sender.run(job,targets,"Notice",[])
    assert t.sent==[(1,"Notice"),(2,"Notice")];assert s.states[job]=={1:"sent",2:"sent"};assert s.finished=="finished"
@pytest.mark.asyncio
async def test_bulk_send_cancel_marks_waiting_targets_cancelled():
    s=StoreFake();sender=BulkSender(s,None);t=TelegramFake(sender);sender.telegram=t;targets=[{"peer_id":1,"title":"A","can_send":1},{"peer_id":2,"title":"B","can_send":1}]
    job=sender.prepare_job(1,"Notice",[],targets);await sender.run(job,targets,"Notice",[])
    assert s.states[job]=={1:"sent",2:"cancelled"}
@pytest.mark.asyncio
async def test_bulk_send_stops_on_telegram_flood_wait():
    s=StoreFake();sender=BulkSender(s,None);t=TelegramFake(flood=True);sender.telegram=t;targets=[{"peer_id":1,"title":"A","can_send":1},{"peer_id":2,"title":"B","can_send":1},{"peer_id":3,"title":"C","can_send":1}]
    job=sender.prepare_job(1,"Notice",[],targets);await sender.run(job,targets,"Notice",[])
    assert s.states[job]=={1:"sent",2:"flood_wait",3:"cancelled"}
@pytest.mark.asyncio
async def test_bulk_send_uses_caption_for_files():
    s=StoreFake();t=TelegramFake();sender=BulkSender(s,t);targets=[{"peer_id":7,"title":"A","can_send":1}]
    job=sender.prepare_job(1,"Notice",["announcement.pdf"],targets);await sender.run(job,targets,"Notice",["announcement.pdf"])
    assert t.sent==[(7,"Notice",("announcement.pdf",))]

@pytest.mark.asyncio
async def test_bulk_send_preserves_individual_message_ids(tmp_path):
    class MultiTelegram(TelegramFake):
        async def send_files(self,p,files,caption=""):
            return [SimpleNamespace(id=31),SimpleNamespace(id=35)]
    paths=[tmp_path/"a.pdf",tmp_path/"b.txt"]
    for path in paths:path.write_bytes(b"test")
    s=StoreFake();sender=BulkSender(s,MultiTelegram());targets=[{"peer_id":7,"title":"A","can_send":1}]
    job=sender.prepare_job(1,"Notice",[str(p) for p in paths],targets)
    await sender.run(job,targets,"Notice",[str(p) for p in paths])
    records=s.attachments[(job,7)]
    assert [(r["name"],r["index"],r["message_id"],r["size"]) for r in records]==[("a.pdf",0,31,4),("b.txt",1,35,4)]
