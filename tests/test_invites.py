from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from telethon import errors, types
from telethon.tl.functions.messages import ExportChatInviteRequest

from academic_chat_manager.telegram_service import TelegramService, invite_error_message


class Client:
    def __init__(self,entity,fail_resolution=False):
        self.entity=entity
        self.fail_resolution=fail_resolution
        self.requests=[]
        self.resolved=[]
        self.link="https://t.me/+example_invite"
    def is_connected(self):return True
    async def get_input_entity(self,value):
        if self.fail_resolution:raise ValueError("not cached")
        if isinstance(self.entity,types.Chat):
            return types.InputPeerChat(chat_id=self.entity.id)
        return types.InputPeerChannel(channel_id=self.entity.id,access_hash=123)
    async def get_entity(self,peer):
        self.resolved.append(peer)
        return self.entity
    async def __call__(self,request,**kwargs):
        self.requests.append((request,kwargs))
        return SimpleNamespace(link=self.link)


def chat():
    return types.Chat(id=7,title="Grup",photo=types.ChatPhotoEmpty(),participants_count=1,date=datetime.now(timezone.utc),version=1)


def channel(username=None):
    return types.Channel(id=7,title="Kanal",photo=types.ChatPhotoEmpty(),date=datetime.now(timezone.utc),access_hash=123,username=username)


@pytest.mark.asyncio
async def test_basic_group_uses_mtproto_export_without_revocation(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client(chat())
    assert await service.export_chat_invite_link(-7)=="https://t.me/+example_invite"
    request,kwargs=service.client.requests[0]
    assert isinstance(request,ExportChatInviteRequest)
    assert isinstance(request.peer,types.InputPeerChat) and request.peer.chat_id==7
    assert not request.legacy_revoke_permanent
    assert kwargs["flood_sleep_threshold"]==0


@pytest.mark.asyncio
async def test_public_channel_uses_public_username_without_creating_invite(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client(channel("university_channel"))
    assert await service.export_chat_invite_link(-1000000000007)=="https://t.me/university_channel"
    assert not service.client.requests


@pytest.mark.asyncio
async def test_private_channel_resolves_using_stored_access_hash(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client(channel(),fail_resolution=True)
    assert await service.export_chat_invite_link(-1000000000007,access_hash=456)=="https://t.me/+example_invite"
    request,_=service.client.requests[0]
    assert isinstance(request.peer,types.InputPeerChannel)
    assert request.peer.channel_id==7 and request.peer.access_hash==456
    with pytest.raises(ValueError,match="eşitleyin"):
        await service.export_chat_invite_link(-1000000000007)


@pytest.mark.asyncio
async def test_personal_chat_and_invalid_response_are_rejected(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client(chat())
    with pytest.raises(ValueError,match="Kişi"):
        await service.export_chat_invite_link(7)
    assert not service.client.requests
    service.client.link=None
    with pytest.raises(ValueError,match="geçerli"):
        await service.export_chat_invite_link(-7)


def test_permission_and_flood_wait_messages_are_localized():
    assert "yönetici" in invite_error_message(errors.ChatAdminRequiredError(None))
    assert "12 saniye" in invite_error_message(errors.FloodWaitError(None,12))
