"""Telegram MTProto integration using Telethon's stable 1.x API."""
from __future__ import annotations
import asyncio
import os
from datetime import timezone
from pathlib import Path
from telethon import TelegramClient, events, errors, types, utils
from telethon.tl.functions.messages import GetHistoryRequest, SendReactionRequest

class TelegramService:
    def __init__(self,session_path:Path):
        self.session_path=Path(session_path); self.client=None; self._code_hash=None; self._phone=None; self._dialogs={}; self.on_message=None
    async def connect(self,api_id:int,api_hash:str):
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
            row={"peer_id":peer_id,"access_hash":access_hash,"title":d.name or "(İsimsiz sohbet)","kind":kind,"username":getattr(ent,"username",None),"can_send":int(can_send),"unread_count":d.unread_count or 0,"last_message":getattr(msg,"message",None) or ("Medya" if getattr(msg,"media",None) else ""),"last_message_at":msg.date.isoformat() if msg and msg.date else None}
            result.append(row); self._dialogs[peer_id]=ent
        return result
    def _entity(self,peer_id):
        if peer_id in self._dialogs:return self._dialogs[peer_id]
        return int(peer_id)
    async def history(self,peer_id,limit=50,before_id=None):
        msgs=await self.client.get_messages(self._entity(peer_id),limit=limit,max_id=before_id or 0)
        rows=[]
        for m in reversed(msgs):
            # Message sender entities are often already present in the Telegram update;
            # do not issue one network request per message while paging history.
            sender=getattr(m,"sender",None)
            sender_name=(" ".join(filter(None,[getattr(sender,"first_name",None),getattr(sender,"last_name",None)])) or getattr(sender,"title",None)) if sender else ("Siz" if m.out else str(m.sender_id or ""))
            file=None
            if m.media:
                f=m.file; file={"name":getattr(f,"name",None) or getattr(f,"ext",None) or "Ek", "size":getattr(f,"size",None),"mime_type":getattr(f,"mime_type",None)}
            reaction_rows=[]
            for item in getattr(getattr(m,"reactions",None),"results",[]) or []:
                emoji=getattr(getattr(item,"reaction",None),"emoticon",None)
                if emoji:reaction_rows.append({"emoji":emoji,"count":int(getattr(item,"count",0) or 0),"chosen":bool(getattr(item,"chosen",False))})
            reply_id=getattr(getattr(m,"reply_to",None),"reply_to_msg_id",None)
            rows.append({"peer_id":peer_id,"message_id":m.id,"sender_id":m.sender_id,"sender_name":sender_name,"text":m.message or "","date":m.date.isoformat() if m.date else None,"outgoing":int(m.out),"media_json":__import__('json').dumps(file,ensure_ascii=False) if file else None,"reactions_json":__import__('json').dumps(reaction_rows,ensure_ascii=False),"reply_to_message_id":reply_id,"message":m})
        return rows
    async def send_text(self,peer_id,text,reply_to=None):return await self.client.send_message(self._entity(peer_id),text,reply_to=reply_to)
    async def export_chat_invite_link(self,peer_id):
        """Create an invite link for a group/channel using the connected account's rights."""
        return await self.client.export_chat_invite_link(self._entity(int(peer_id)))
    async def send_reaction(self,peer_id,message_id,emoji):
        request=SendReactionRequest(peer=self._entity(int(peer_id)),msg_id=int(message_id),reaction=[types.ReactionEmoji(emoticon=str(emoji))])
        return await self.client(request)
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
        return await msg.download_media(file=str(destination))
    async def edit_message(self,peer_id,message_id,text):return await self.client.edit_message(self._entity(peer_id),message_id,text)
    async def delete_message(self,peer_id,message_id,revoke=True):return await self.client.delete_messages(self._entity(peer_id),message_id,revoke=revoke)
    async def search_messages(self,peer_id,query,limit=50):return await self.client.get_messages(self._entity(peer_id),search=query,limit=limit)
    def start_updates(self,handler):
        """Forward Telegram message updates to the UI without changing read state."""
        async def on_new_message(event):
            m=event.message; peer_id=utils.get_peer_id(event.message.peer_id); sender=getattr(m,"sender",None)
            name=(" ".join(filter(None,[getattr(sender,"first_name",None),getattr(sender,"last_name",None)])) or getattr(sender,"title",None)) if sender else ("Siz" if m.out else str(m.sender_id or ""))
            media=None
            if m.media:
                f=m.file; media={"name":getattr(f,"name",None) or getattr(f,"ext",None) or "Ek","size":getattr(f,"size",None),"mime_type":getattr(f,"mime_type",None)}
            row={"peer_id":peer_id,"chat_title":getattr(event.chat,"title",None) or getattr(event.chat,"first_name",None) or name,"message_id":m.id,"sender_id":m.sender_id,"sender_name":name,"text":m.message or "","date":m.date.isoformat() if m.date else None,"outgoing":int(m.out),"media_json":__import__('json').dumps(media,ensure_ascii=False) if media else None,"message":m}
            result=handler(row)
            if hasattr(result,"__await__"):await result
        self.client.add_event_handler(on_new_message,events.NewMessage())
    async def disconnect(self):
        if self.client:await self.client.disconnect();self.client=None
    async def log_out(self):
        if self.client and self.client.is_connected():await self.client.log_out()
        await self.disconnect()
