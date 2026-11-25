"""Telegram MTProto integration using Telethon's stable 1.x API."""
from __future__ import annotations
import asyncio
import os
import tempfile
import time
import re
from datetime import timezone
from pathlib import Path
from telethon import TelegramClient, events, errors, types, utils
from telethon.tl.functions.messages import GetHistoryRequest, SendReactionRequest, GetMessagesReactionsRequest, ExportChatInviteRequest
from telethon.tl.functions.help import GetAppConfigRequest
try:
    from .media import media_metadata
except ImportError:
    from media import media_metadata

def invite_error_message(error):
    if isinstance(error,errors.FloodWaitError):
        return f"Telegram {error.seconds} saniye bekleme istedi; daha sonra yeniden deneyin."
    code=str(getattr(error,"message","")).upper()
    translations={
        "CHAT_ADMIN_REQUIRED":"Davet bağlantısı oluşturmak için yönetici ve kullanıcı davet etme yetkisi gerekiyor.",
        "CHAT_WRITE_FORBIDDEN":"Bu sohbette davet bağlantısı oluşturma yetkiniz yok.",
        "CHANNEL_PRIVATE":"Özel gruba veya kanala erişiminiz yok.",
        "CHANNEL_INVALID":"Kanal veya grup artık geçerli değil.",
        "CHAT_ID_INVALID":"Grup kimliği artık geçerli değil; sohbetleri eşitleyin.",
        "PEER_ID_INVALID":"Sohbet bulunamadı; sohbetleri eşitleyin.",
        "CHANNEL_MONOFORUM_UNSUPPORTED":"Bu sohbet türü davet bağlantısını desteklemiyor.",
    }
    # Generated Telethon RPC errors do not always expose the symbolic RPC code
    # in .message; use their class names as an additional stable lookup.
    by_class={"".join(word.title() for word in key.split("_"))+"Error":value for key,value in translations.items()}
    return translations.get(code) or by_class.get(type(error).__name__) or str(error).strip() or type(error).__name__


def edit_metadata(message):
    """Telegram may suppress the edited label while still providing an edit date."""
    date=getattr(message,"edit_date",None)
    return {"edit_date":date.isoformat() if date else None,
            "edit_hidden":int(bool(getattr(message,"edit_hide",False)))}


def edited_message_row(message,peer_id):
    media=media_metadata(message)
    return {"peer_id":peer_id,"message_id":message.id,"text":message.message or "",
            "media_json":__import__("json").dumps(media,ensure_ascii=False) if media else None,
            **edit_metadata(message)}


def emoji_key(emoji):
    return str(emoji).replace("\ufe0f", "").replace("\ufe0e", "")


def reaction_rows(message):
    rows=[]
    for item in getattr(getattr(message,"reactions",None),"results",[]) or []:
        emoji=getattr(getattr(item,"reaction",None),"emoticon",None)
        if emoji:
            order=getattr(item,"chosen_order",None)
            rows.append({"emoji":emoji,"count":int(getattr(item,"count",0) or 0),"chosen":order is not None,"chosen_order":order})
    return rows


def next_reactions(message,emoji,limit):
    """Return the complete desired list, excluding paid reactions."""
    selected=[]
    for item in getattr(getattr(message,"reactions",None),"results",[]) or []:
        order=getattr(item,"chosen_order",None)
        reaction=getattr(item,"reaction",None)
        if order is not None and isinstance(reaction,(types.ReactionEmoji,types.ReactionCustomEmoji)):
            selected.append((order,reaction))
    current=[reaction for _,reaction in sorted(selected,key=lambda pair:pair[0])]
    key=emoji_key(emoji)
    remaining=[reaction for reaction in current if not isinstance(reaction,types.ReactionEmoji) or emoji_key(reaction.emoticon)!=key]
    if len(remaining)!=len(current):
        return remaining,"removed"
    desired=remaining+[types.ReactionEmoji(emoticon=str(emoji))]
    return desired[-max(1,limit):],"replaced" if len(desired)>limit else "added"


class TelegramService:
    def __init__(self,session_path:Path):
        self.session_path=Path(session_path); self.client=None; self._code_hash=None; self._phone=None; self._dialogs={}; self._read_outbox_max_ids={}; self.on_message=None
        self._reaction_lock=asyncio.Lock();self._reaction_limit_cache=None
    async def connect(self,api_id:int,api_hash:str):
        self._reaction_limit_cache=None
        self.client=TelegramClient(str(self.session_path),api_id,api_hash,connection_retries=5,request_retries=3,auto_reconnect=True,timeout=15)
        await self.client.connect()
        session_file=Path(str(self.session_path)+".session")
        if os.name!="nt" and session_file.exists():session_file.chmod(0o600)
        if await self.client.is_user_authorized(): return {"authorized":True,"user":await self.client.get_me()}
        return {"authorized":False}
    async def request_code(self,phone):
        self._phone=phone
        sent=await self.client.send_code_request(phone); self._code_hash=sent.phone_code_hash
        return sent
    async def sign_in(self,phone,code,password=None):
        try:
            if password: user=await self.client.sign_in(password=password)
            else:user=await self.client.sign_in(phone=phone,code=code,phone_code_hash=self._code_hash)
            return {"authorized":True,"user":user}
        except errors.SessionPasswordNeededError:return {"authorized":False,"needs_password":True}
    async def request_sign_in_code(self,phone,code):return await self.sign_in(phone,code)
    async def load_dialogs(self):
        dialogs=await self.client.get_dialogs(limit=None)
        result=[]
        for d in dialogs:
            ent=d.entity; peer_id=utils.get_peer_id(ent); access_hash=getattr(ent,"access_hash",None)
            if isinstance(ent,(types.User,types.UserEmpty)):kind="Bot" if getattr(ent,"bot",False) else "Kişi"
            elif isinstance(ent,types.Channel):kind="Kanal" if getattr(ent,"broadcast",False) else "Grup"
            else:kind="Grup"
            can_send=not getattr(ent,"restricted",False) and not getattr(ent,"left",False) and not (isinstance(ent,types.Channel) and getattr(ent,"broadcast",False) and not (getattr(ent,"creator",False) or getattr(getattr(ent,"admin_rights",None),"post_messages",False)))
            msg=d.message
            outgoing=bool(getattr(msg,"out",False));read_max=int(getattr(d.dialog,"read_outbox_max_id",0) or 0)
            self._read_outbox_max_ids[peer_id]=max(self._read_outbox_max_ids.get(peer_id,0),read_max)
            row={"peer_id":peer_id,"access_hash":access_hash,"title":d.name or "(İsimsiz sohbet)","kind":kind,"username":getattr(ent,"username",None),"can_send":int(can_send),"unread_count":d.unread_count or 0,"last_message":getattr(msg,"message",None) or ("Medya" if getattr(msg,"media",None) else ""),"last_message_at":msg.date.isoformat() if msg and msg.date else None,"last_message_id":getattr(msg,"id",None),"last_message_outgoing":int(outgoing),"last_message_read":int(outgoing and msg is not None and msg.id<=read_max)}
            result.append(row); self._dialogs[peer_id]=ent
        return result
    def _entity(self,peer_id):
        if peer_id in self._dialogs:return self._dialogs[peer_id]
        return int(peer_id)
    def is_message_read(self,peer_id,message_id):
        return bool(message_id and int(message_id)<=self._read_outbox_max_ids.get(int(peer_id),0))
    async def history(self,peer_id,limit=50,before_id=None):
        msgs=await self.client.get_messages(self._entity(peer_id),limit=limit,max_id=before_id or 0)
        rows=[]
        for m in reversed(msgs):
            # Message sender entities are often already present in the Telegram update;
            # do not issue one network request per message while paging history.
            sender=getattr(m,"sender",None)
            sender_name=(" ".join(filter(None,[getattr(sender,"first_name",None),getattr(sender,"last_name",None)])) or getattr(sender,"title",None)) if sender else ("Siz" if m.out else str(m.sender_id or ""))
            file=media_metadata(m)
            reactions=reaction_rows(m)
            reply_id=getattr(getattr(m,"reply_to",None),"reply_to_msg_id",None)
            rows.append({"peer_id":peer_id,"message_id":m.id,"sender_id":m.sender_id,"sender_name":sender_name,"text":m.message or "","date":m.date.isoformat() if m.date else None,"outgoing":int(m.out),"read":int(bool(m.out and self.is_message_read(peer_id,m.id))),"media_json":__import__('json').dumps(file,ensure_ascii=False) if file else None,"reactions_json":__import__('json').dumps(reactions,ensure_ascii=False),"reply_to_message_id":reply_id,**edit_metadata(m),"message":m})
        return rows
    async def send_text(self,peer_id,text,reply_to=None):return await self.client.send_message(self._entity(peer_id),text,reply_to=reply_to)
    async def export_chat_invite_link(self,peer_id,access_hash=None):
        """Return a public URL or create an additional private invite; never revoke existing links."""
        if not self.client or not self.client.is_connected():
            raise ConnectionError("Telegram hesabı bağlı değil.")
        peer_id=int(peer_id)
        real_id,peer_type=utils.resolve_id(peer_id)
        if peer_type not in (types.PeerChat,types.PeerChannel):
            raise ValueError("Kişi ve bot sohbetleri için davet bağlantısı oluşturulamaz.")
        try:
            peer=await self.client.get_input_entity(self._entity(peer_id))
        except (ValueError,TypeError):
            if peer_type is types.PeerChat:
                peer=types.InputPeerChat(chat_id=real_id)
            elif access_hash is not None:
                peer=types.InputPeerChannel(channel_id=real_id,access_hash=int(access_hash))
            else:
                raise ValueError("Sohbet bilgisi bulunamadı; Ayarlar bölümünden sohbetleri eşitleyin.") from None
        entity=await self.client.get_entity(peer)
        if isinstance(entity,types.Chat) and getattr(entity,"migrated_to",None):
            peer=await self.client.get_input_entity(entity.migrated_to)
            entity=await self.client.get_entity(peer)
        if not isinstance(entity,(types.Chat,types.Channel)) or getattr(entity,"left",False) or getattr(entity,"deactivated",False):
            raise ValueError("Grup veya kanal erişilebilir değil; sohbetleri eşitleyin.")
        username=getattr(entity,"username",None)
        if not username:
            username=next((entry.username for entry in getattr(entity,"usernames",None) or [] if getattr(entry,"active",False)),None)
        if isinstance(entity,types.Channel) and username and re.fullmatch(r"[A-Za-z0-9_]+",username):
            return "https://t.me/"+username
        # MTProto uses a raw ExportChatInviteRequest, not a Bot API-style client method.
        # The default request does not revoke existing invites or set usage/expiry limits.
        result=await self.client(ExportChatInviteRequest(peer=peer),flood_sleep_threshold=0)
        link=getattr(result,"link",None)
        if not isinstance(link,str) or not re.fullmatch(r"https://t\.me/(?:\+|joinchat/)[A-Za-z0-9_-]+",link):
            raise ValueError("Telegram geçerli bir davet bağlantısı döndürmedi.")
        return link
    async def _reaction_limit(self):
        now=time.monotonic()
        if self._reaction_limit_cache and now-self._reaction_limit_cache[0]<300:
            return self._reaction_limit_cache[1]
        user=await self.client.get_me()
        premium=bool(getattr(user,"premium",False))
        key="reactions_user_max_premium" if premium else "reactions_user_max_default"
        limit=3 if premium else 1
        try:
            response=await self.client(GetAppConfigRequest(hash=0))
            for entry in getattr(getattr(response,"config",None),"value",[]) or []:
                if getattr(entry,"key",None)==key:
                    value=getattr(getattr(entry,"value",None),"value",None)
                    if isinstance(value,(int,float)) and value>=1:limit=int(value)
                    break
        except errors.FloodWaitError:
            raise
        except errors.RPCError:
            # Telegram documents these defaults if app config is unavailable.
            pass
        self._reaction_limit_cache=(now,limit)
        return limit

    @staticmethod
    def _reaction_update(result,peer_id,message_id):
        for update in getattr(result,"updates",[]) or []:
            if isinstance(update,types.UpdateMessageReactions) and update.msg_id==message_id and utils.get_peer_id(update.peer)==int(peer_id) and not getattr(update.reactions,"min",False):
                return update
        return None

    async def _full_reaction_message(self,peer,peer_id,message_id):
        message=await self.client.get_messages(peer,ids=message_id)
        if not message or isinstance(message,types.MessageEmpty):raise ValueError("Telegram mesajı bulunamadı")
        if getattr(getattr(message,"reactions",None),"min",False):
            updates=await self.client(GetMessagesReactionsRequest(peer=peer,id=[message_id]))
            message=self._reaction_update(updates,peer_id,message_id)
            if message is None:raise ValueError("Mesajın güncel tepki bilgisi alınamadı")
        return message

    async def send_reaction(self,peer_id,message_id,emoji):
        # Serialize read/modify/write so rapid clicks cannot overwrite one another.
        async with self._reaction_lock:
            peer=self._entity(int(peer_id));message_id=int(message_id)
            message=await self._full_reaction_message(peer,peer_id,message_id)
            desired,outcome=next_reactions(message,emoji,await self._reaction_limit())
            # The official desktop client omits the optional reaction vector when clearing the last reaction.
            try:
                result=await self.client(SendReactionRequest(peer=peer,msg_id=message_id,reaction=desired or None,add_to_recent=outcome!="removed"))
            except errors.MessageNotModifiedError:
                result=None
                outcome="unchanged"
            update=self._reaction_update(result,peer_id,message_id)
            if update is not None:return outcome,reaction_rows(update)
            # Fetch the exact message, including older/search results, not just latest history.
            try:
                updated=await self._full_reaction_message(peer,peer_id,message_id)
                return outcome,reaction_rows(updated)
            except Exception:
                # The mutation succeeded; do not report it as a failed send.
                return outcome,None
    async def mark_read(self,peer_id,max_id):return await self.client.send_read_acknowledge(self._entity(peer_id),max_id=max_id)
    async def send_files(self,peer_id,paths,caption="",progress_callback=None,reply_to=None):
        paths=[str(Path(p)) for p in paths]
        if not paths:raise ValueError("Dosya seçilmedi")
        # Telethon accepts multiple file paths as an album when possible; groups over 10 split into chunks.
        sent=[]
        for i in range(0,len(paths),10):
            batch=paths[i:i+10]; caption_text=caption if i==0 else ""
            async def progress(current,total):
                if progress_callback: progress_callback(i+current,total)
            result=await self.client.send_file(self._entity(peer_id),batch,caption=caption_text,progress_callback=progress,reply_to=reply_to)
            sent.extend(result if isinstance(result,list) else [result])
        return sent
    async def download_media(self,peer_id,message_id,destination):
        msg=await self.client.get_messages(self._entity(peer_id),ids=message_id)
        if not msg:raise FileNotFoundError("Telegram mesajı bulunamadı")
        if media_metadata(msg) is None:
            raise ValueError("Mesaj indirilebilir bir dosya veya fotoğraf içermiyor")
        destination=Path(destination)
        temporary=None
        try:
            # Do not replace an existing file until Telegram has completed the transfer.
            with tempfile.NamedTemporaryFile(mode="wb",dir=destination.parent,prefix=".acm-",suffix=".part",delete=False) as stream:
                temporary=Path(stream.name)
                result=await msg.download_media(file=stream)
                if result is None:
                    raise IOError("Telegram dosyayı döndürmedi")
            os.replace(temporary,destination)
            return str(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    async def download_media_bytes(self,peer_id,message_id,max_bytes=12*1024*1024):
        """Load a small image for an in-chat preview without creating a user file."""
        msg=await self.client.get_messages(self._entity(peer_id),ids=message_id)
        if not msg:raise FileNotFoundError("Telegram mesajı bulunamadı")
        metadata=media_metadata(msg)
        if not metadata or not str(metadata.get("mime_type") or "").lower().startswith("image/"):
            return None
        oversized=isinstance(metadata.get("size"),int) and metadata["size"]>max_bytes
        data=await msg.download_media(file=bytes,thumb=0) if oversized else await msg.download_media(file=bytes)
        if data is not None and len(data)>max_bytes:
            return None
        return data
    async def download_profile_photo(self,peer_id):
        """Return a peer's current profile photo in memory, or None if it has none."""
        return await self.client.download_profile_photo(self._entity(peer_id),file=bytes)
    async def edit_message(self,peer_id,message_id,text):return await self.client.edit_message(self._entity(peer_id),message_id,text)
    async def delete_message(self,peer_id,message_id,revoke=True):return await self.client.delete_messages(self._entity(peer_id),message_id,revoke=revoke)
    async def search_messages(self,peer_id,query,limit=50):return await self.client.get_messages(self._entity(peer_id),search=query,limit=limit)
    def start_updates(self,handler,edit_handler=None,read_handler=None):
        """Forward Telegram message updates to the UI without changing read state."""
        async def on_new_message(event):
            m=event.message; peer_id=utils.get_peer_id(event.message.peer_id); sender=getattr(m,"sender",None)
            name=(" ".join(filter(None,[getattr(sender,"first_name",None),getattr(sender,"last_name",None)])) or getattr(sender,"title",None)) if sender else ("Siz" if m.out else str(m.sender_id or ""))
            media=media_metadata(m)
            row={"peer_id":peer_id,"chat_title":getattr(event.chat,"title",None) or getattr(event.chat,"first_name",None) or name,"message_id":m.id,"sender_id":m.sender_id,"sender_name":name,"text":m.message or "","date":m.date.isoformat() if m.date else None,"outgoing":int(m.out),"read":int(bool(m.out and self.is_message_read(peer_id,m.id))),"media_json":__import__('json').dumps(media,ensure_ascii=False) if media else None,"reactions_json":__import__('json').dumps(reaction_rows(m),ensure_ascii=False),**edit_metadata(m),"message":m}
            result=handler(row)
            if hasattr(result,"__await__"):await result
        self.client.add_event_handler(on_new_message,events.NewMessage())
        if edit_handler is not None:
            async def on_edited_message(event):
                m=event.message
                row=edited_message_row(m,utils.get_peer_id(m.peer_id))
                result=edit_handler(row)
                if hasattr(result,"__await__"):await result
            self.client.add_event_handler(on_edited_message,events.MessageEdited())
        if read_handler is not None:
            async def on_message_read(event):
                if not getattr(event,"outbox",False):return
                peer=getattr(event,"peer",None);max_id=getattr(event,"max_id",None)
                if peer is None or not max_id:return
                peer_id=utils.get_peer_id(peer)
                self._read_outbox_max_ids[peer_id]=max(self._read_outbox_max_ids.get(peer_id,0),int(max_id))
                result=read_handler(peer_id,int(max_id))
                if hasattr(result,"__await__"):await result
            self.client.add_event_handler(on_message_read,events.MessageRead())
    async def disconnect(self):
        if self.client:await self.client.disconnect();self.client=None
    async def log_out(self):
        if self.client and self.client.is_connected():await self.client.log_out()
        await self.disconnect()
