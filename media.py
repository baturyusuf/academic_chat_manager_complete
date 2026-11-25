"""Attachment metadata and safe download references shared by chat and bulk history."""
from __future__ import annotations

import json
import mimetypes
import ntpath
import re
from pathlib import Path


def safe_filename(value, fallback="telegram_file"):
    """Treat remote names as labels, never as paths or Windows device names."""
    name = ntpath.basename(str(value or "").replace("/", "\\"))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name:
        name = fallback
    if re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", name.split(".")[0], re.I):
        name = "_" + name
    return name[:240].rstrip(" .") or fallback


def media_metadata(message):
    """Extract a downloadable document/photo, not a webpage or other media placeholder."""
    from telethon import types
    if not isinstance(getattr(message, "media", None), (types.MessageMediaPhoto, types.MessageMediaDocument)):
        return None
    file = getattr(message, "file", None)
    if file is None:
        return None
    mime = getattr(file, "mime_type", None)
    ext = getattr(file, "ext", None) or mimetypes.guess_extension(mime or "") or ""
    name = getattr(file, "name", None) or f"Ek_{message.id}{ext}"
    return {"name": safe_filename(name), "size": getattr(file, "size", None), "mime_type": mime}


def decode_media(value):
    try:
        data = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("name") else None


def format_size(size):
    if not isinstance(size, (int, float)) or isinstance(size, bool) or size < 0:
        return "Boyut bilinmiyor"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def local_metadata(path):
    name = safe_filename(path)
    try:
        size = Path(path).stat().st_size
    except OSError:
        size = None
    return {"name": name, "size": size, "mime_type": mimetypes.guess_type(name)[0]}


def bulk_sent_attachments(paths, messages):
    """Telegram returns one message per file in upload order. Never guess on mismatch."""
    if len(paths) != len(messages) or any(not getattr(m, "id", None) for m in messages):
        return []
    result = []
    for index, (path, message) in enumerate(zip(paths, messages)):
        metadata = media_metadata(message) or local_metadata(path)
        result.append({**metadata, "name": safe_filename(path), "index": index, "message_id": message.id})
    return result


def bulk_attachment_cards(paths, targets):
    """Resolve each original file to one successfully sent Telegram message.

    Legacy single-file jobs can use the stored last message ID. Legacy multi-file
    jobs lack a trustworthy index-to-ID mapping and are deliberately not guessed.
    """
    cards = [local_metadata(path) for path in paths]
    for target in targets:
        if target.get("status") != "sent":
            continue
        try:
            records = json.loads(target.get("attachments_json") or "[]")
        except (TypeError, ValueError):
            records = []
        if not isinstance(records, list):
            records = []
        if not records and len(cards) == 1 and target.get("telegram_message_id"):
            records = [{"index": 0, "message_id": target["telegram_message_id"]}]
        for record in records:
            if not isinstance(record, dict):
                continue
            index = record.get("index")
            if type(index) is not int or not 0 <= index < len(cards) or not record.get("message_id"):
                continue
            if cards[index].get("message_id"):
                continue
            cards[index].update({key: record[key] for key in ("name", "size", "mime_type") if key in record})
            cards[index].update(peer_id=target["peer_id"], message_id=record["message_id"])
    return cards
