import json
from types import SimpleNamespace

import pytest
from telethon import types

from academic_chat_manager.media import (
    bulk_attachment_cards, bulk_sent_attachments, decode_media,
    format_size, media_metadata, safe_filename,
)
from academic_chat_manager.telegram_service import TelegramService


def test_photo_metadata_without_original_filename():
    message=SimpleNamespace(id=42,media=types.MessageMediaPhoto(),file=SimpleNamespace(name=None,ext=".jpg",size=2048,mime_type="image/jpeg"))
    assert media_metadata(message)=={"name":"Ek_42.jpg","size":2048,"mime_type":"image/jpeg"}
    assert format_size(2048)=="2.0 KB"
    assert media_metadata(SimpleNamespace(media=types.MessageMediaEmpty(),file=None)) is None
    assert decode_media("[]") is None
    assert safe_filename(r"..\..\CON.txt")=="_CON.txt"


def test_bulk_attachment_resolution_without_local_files(tmp_path):
    paths=[str(tmp_path/"a.pdf"),str(tmp_path/"b.txt")]
    records=[{"index":0,"name":"a.pdf","size":1024,"message_id":31},{"index":1,"name":"b.txt","size":2048,"message_id":35}]
    targets=[{"peer_id":-1,"status":"failed"},{"peer_id":-2,"status":"sent","telegram_message_id":35,"attachments_json":json.dumps(records)}]
    cards=bulk_attachment_cards(paths,targets)
    assert [(c["peer_id"],c["message_id"],c["size"]) for c in cards]==[(-2,31,1024),(-2,35,2048)]
    legacy=[{"peer_id":-2,"status":"sent","telegram_message_id":35}]
    assert "message_id" not in bulk_attachment_cards(paths,legacy)[0]
    assert bulk_attachment_cards(paths[:1],legacy)[0]["message_id"]==35
    assert bulk_sent_attachments(paths,[SimpleNamespace(id=35)])==[]


@pytest.mark.asyncio
async def test_download_does_not_replace_existing_file_on_failure(tmp_path):
    destination=tmp_path/"a.pdf"
    destination.write_bytes(b"original")
    class Message:
        id=42
        media=types.MessageMediaDocument()
        file=SimpleNamespace(name="a.pdf",size=3,ext=".pdf",mime_type="application/pdf")
        fail=True
        async def download_media(self,file):
            file.write(b"new")
            if self.fail:
                raise IOError("interrupted")
            return file
    message=Message()
    class Client:
        async def get_messages(self,peer,ids):
            assert (peer,ids)==(-1,42)
            return message
    service=TelegramService(tmp_path/"session")
    service.client=Client()
    with pytest.raises(IOError):
        await service.download_media(-1,42,destination)
    assert destination.read_bytes()==b"original"
    assert not list(tmp_path.glob("*.part"))
    message.fail=False
    assert await service.download_media(-1,42,destination)==str(destination)
    assert destination.read_bytes()==b"new"
    assert not list(tmp_path.glob("*.part"))
