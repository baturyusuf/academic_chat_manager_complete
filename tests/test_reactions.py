import asyncio
from types import SimpleNamespace

import pytest
from telethon import types
from telethon.tl.functions.help import GetAppConfigRequest
from telethon.tl.functions.messages import SendReactionRequest

from academic_chat_manager.telegram_service import TelegramService, next_reactions, reaction_rows


def count(emoji,order=None,total=1):
    return types.ReactionCount(reaction=types.ReactionEmoji(emoticon=emoji),count=total,chosen_order=order)


def message(*counts):
    return SimpleNamespace(reactions=SimpleNamespace(results=list(counts)))


def emojis(reactions):
    return [r.emoticon for r in (reactions or []) if isinstance(r,types.ReactionEmoji)]


def test_chosen_order_zero_is_selected_and_other_users_are_not_selected():
    rows=reaction_rows(message(count("👍",0,4),count("😂",None,10)))
    assert rows==[
        {"emoji":"👍","count":4,"chosen":True,"chosen_order":0},
        {"emoji":"😂","count":10,"chosen":False,"chosen_order":None},
    ]


def test_same_reaction_toggles_off_and_variation_selectors_are_equivalent():
    desired,outcome=next_reactions(message(count("❤",0),count("👍",1)),"❤️",3)
    assert emojis(desired)==["👍"] and outcome=="removed"
    desired,outcome=next_reactions(message(count("👍",0)),"👍",1)
    assert desired==[] and outcome=="removed"


def test_new_reaction_replaces_oldest_only_when_account_limit_reached():
    desired,outcome=next_reactions(message(count("👍",0),count("😂",None)),"🔥",1)
    assert emojis(desired)==["🔥"] and outcome=="replaced"
    desired,outcome=next_reactions(message(count("😂",2),count("👍",0)),"🔥",3)
    assert emojis(desired)==["👍","😂","🔥"] and outcome=="added"
    desired,outcome=next_reactions(message(count("😂",2),count("👍",0),count("🙏",1)),"🔥",3)
    assert emojis(desired)==["🙏","😂","🔥"] and outcome=="replaced"


def test_existing_custom_reaction_is_preserved_within_limit():
    custom=types.ReactionCount(reaction=types.ReactionCustomEmoji(document_id=123),count=1,chosen_order=0)
    desired,outcome=next_reactions(message(custom),"👍",3)
    assert desired[0].document_id==123 and emojis(desired)==["👍"] and outcome=="added"


class Client:
    def __init__(self,premium=False,limit=1):
        self.premium=premium;self.limit=limit;self.current=message();self.requests=[];self.lookups=[]
        self.config_calls=0;self.fail_refresh=False
    async def get_me(self):
        return SimpleNamespace(premium=self.premium)
    async def get_messages(self,peer,ids):
        self.lookups.append((peer,ids))
        if self.fail_refresh and self.requests:
            raise IOError("refresh failed")
        return self.current
    async def __call__(self,request):
        if isinstance(request,GetAppConfigRequest):
            self.config_calls+=1
            key="reactions_user_max_premium" if self.premium else "reactions_user_max_default"
            return SimpleNamespace(config=SimpleNamespace(value=[SimpleNamespace(key=key,value=SimpleNamespace(value=self.limit))]))
        assert isinstance(request,SendReactionRequest)
        self.requests.append(request)
        self.current=message(*(count(emoji,i) for i,emoji in enumerate(emojis(request.reaction))))
        await asyncio.sleep(0)
        return SimpleNamespace(updates=[])


@pytest.mark.asyncio
async def test_service_serializes_rapid_reactions_and_reuses_account_config(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client(premium=True,limit=2)
    results=await asyncio.gather(service.send_reaction(-5,42,"👍"),service.send_reaction(-5,42,"🔥"))
    assert [outcome for outcome,_ in results]==["added","added"]
    assert [emojis(request.reaction) for request in service.client.requests]==[["👍"],["👍","🔥"]]
    assert service.client.config_calls==1
    assert all(pair==(-5,42) for pair in service.client.lookups)
    outcome,rows=await service.send_reaction(-5,42,"👍")
    assert outcome=="removed" and emojis(service.client.requests[-1].reaction)==["🔥"]
    assert rows[0]["chosen"] is True
    outcome,rows=await service.send_reaction(-5,42,"🔥")
    assert outcome=="removed" and service.client.requests[-1].reaction is None and rows==[]


@pytest.mark.asyncio
async def test_successful_reaction_is_not_reported_as_failed_if_refresh_fails(tmp_path):
    service=TelegramService(tmp_path/"session")
    service.client=Client()
    service.client.fail_refresh=True
    assert await service.send_reaction(-5,42,"👍")==("added",None)
    assert len(service.client.requests)==1

@pytest.mark.asyncio
async def test_unchanged_server_response_refreshes_without_failure(tmp_path):
    from telethon import errors
    class Unchanged(Client):
        async def __call__(self,request):
            if isinstance(request,SendReactionRequest):
                self.current=message(count("👍",0))
                raise errors.MessageNotModifiedError(request)
            return await super().__call__(request)
    service=TelegramService(tmp_path/"session")
    service.client=Unchanged()
    outcome,rows=await service.send_reaction(-5,42,"👍")
    assert outcome=="unchanged" and rows[0]["chosen"] is True
