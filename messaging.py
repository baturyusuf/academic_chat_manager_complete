"""Confirmed, durable bulk-send orchestration. FloodWait is respected as reported by Telegram."""
from __future__ import annotations
import asyncio, uuid
from telethon import errors

class BulkSender:
    def __init__(self,store,telegram):self.store=store;self.telegram=telegram;self.cancel_event=asyncio.Event();self.current_job=None
    def preview_targets(self,collection_id,include_children=True):
        return self.store.collection_chats(collection_id,include_descendants=include_children)
    def prepare_job(self,collection_id,message,files,selected_targets,collection_ids=None):
        if not message.strip() and not files:raise ValueError("Gönderilecek metin veya dosya ekleyin")
        allowed=[t for t in selected_targets if t.get("can_send")]
        if not allowed:raise ValueError("Gönderim yetkisi olan sohbet seçilmedi")
        self.cancel_event.clear();job_id=str(uuid.uuid4())
        if collection_ids is None:self.store.create_job(job_id,collection_id,message,files,allowed)
        else:self.store.create_job(job_id,collection_id,message,files,allowed,collection_ids=collection_ids)
        return job_id
    async def run(self,job_id,targets,message,files):
        self.current_job=job_id; failures=0
        if hasattr(self.store,"set_job_status"):self.store.set_job_status(job_id,"running")
        for target in targets:
            peer_id=target["peer_id"]
            state=next((row["status"] for row in self.store.job_targets(job_id) if row["peer_id"]==peer_id),None) if hasattr(self.store,"job_targets") else None
            if state in ("cancelled","sent"):
                continue
            if self.cancel_event.is_set():self.store.update_target(job_id,peer_id,"cancelled");continue
            self.store.update_target(job_id,peer_id,"sending")
            try:
                sent=[]
                if files:sent.extend(await self.telegram.send_files(peer_id,files,caption=message.strip()))
                elif message.strip():sent.append(await self.telegram.send_text(peer_id,message))
                self.store.update_target(job_id,peer_id,"sent",message_id=getattr(sent[-1],"id",None))
            except errors.FloodWaitError as e:
                # Do not bypass Telegram limits. Keep this item queued for explicit later retry.
                self.store.update_target(job_id,peer_id,"flood_wait",f"Telegram {e.seconds} saniye bekleme istedi")
                failures+=1
                # Stop the batch instead of trying to wait around or routing through another account.
                for remaining in targets[targets.index(target)+1:]:self.store.update_target(job_id,remaining["peer_id"],"cancelled","FloodWait nedeniyle kuyruk durduruldu")
                break
            except Exception as e:
                self.store.update_target(job_id,peer_id,"failed",str(e)); failures+=1
            await asyncio.sleep(0.35)
        states=[row["status"] for row in self.store.job_targets(job_id)] if hasattr(self.store,"job_targets") else []
        was_cancelled=any(state=="cancelled" for state in states)
        self.store.finish_job(job_id,"partial" if failures or (was_cancelled and any(state=="sent" for state in states)) else ("cancelled" if was_cancelled or self.cancel_event.is_set() else "finished"));self.current_job=None
    def cancel(self):self.cancel_event.set()
