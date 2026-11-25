import asyncio
from datetime import datetime
from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from academic_chat_manager import main
from academic_chat_manager.storage import Store


def test_chat_refresh_keeps_message_widgets_embedded(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(main, "Store", lambda: Store(tmp_path / "chat-refresh.sqlite3"))
    monkeypatch.setattr(main.security, "get_secret", lambda key: None)
    monkeypatch.setattr(main, "PREFS", main.QSettings(str(tmp_path / "ui.ini"), main.QSettings.IniFormat))
    main.PREFS.setValue("onboarding/dismissed", True)
    window = main.MainWindow()
    window.show()
    app.processEvents()

    opened_windows = []

    class WindowWatcher(QObject):
        def eventFilter(self, widget, event):
            # Show is synchronous, so this catches windows even if the layout
            # reparents them before control returns to the event loop.
            if event.type() == QEvent.Show and isinstance(widget, QWidget) and widget.isWindow():
                opened_windows.append(widget.objectName() or type(widget).__name__)
            return False

    watcher = WindowWatcher()
    app.installEventFilter(watcher)
    date = "2026-11-25T12:00:00+00:00"

    def message(peer_id, message_id, outgoing=False):
        return {"peer_id": peer_id, "message_id": message_id, "sender_id": 3,
                "sender_name": "Ayşe", "text": f"Mesaj {message_id}", "date": date,
                "outgoing": int(outgoing), "media_json": None,
                "reactions_json": '[{"emoji":"👍","count":1}]'}

    history = {
        -101: [message(-101, index, index % 2 == 0) for index in range(1, 101)],
        102: [message(102, 1), message(102, 2, True)],
    }

    class Telegram:
        client = SimpleNamespace(is_connected=lambda: True)

        async def history(self, peer_id, limit, before):
            return history[peer_id][-limit:]

        async def mark_read(self, peer_id, message_id):
            pass

        async def send_text(self, peer_id, text, reply_to=None):
            row = {**message(peer_id, 102, True), "text": text}
            history[peer_id].append(row)
            window._on_live_message(row)
            return SimpleNamespace(id=102, date=datetime.fromisoformat(date))

        async def download_profile_photo(self, peer_id):
            return None

    def displayed_rows():
        return {item.data(Qt.UserRole)["message_id"]: window.messages.itemWidget(item)
                for item in (window.messages.item(i) for i in range(window.messages.count()))}

    async def switch_chat(peer_id):
        for index in range(window.chat_list.count()):
            item = window.chat_list.item(index)
            if item.data(Qt.UserRole) == peer_id:
                window.chat_list.setCurrentItem(item, main.QItemSelectionModel.ClearAndSelect)
                break
        await asyncio.sleep(0)
        app.processEvents()
        assert window.selected_peer == peer_id

    async def exercise():
        await switch_chat(102)
        assert list(displayed_rows()) == [1, 2]
        await switch_chat(-101)
        original = displayed_rows()
        assert list(original) == list(range(1, 101))
        assert not opened_windows, opened_windows[:10]

        incoming = message(-101, 101)
        history[-101].append(incoming)
        window._on_live_message(incoming)
        after_receive = displayed_rows()
        assert list(after_receive) == list(range(2, 102))
        assert all(after_receive[index] is original[index] for index in range(2, 101))

        window.message_input.setPlainText("Gönderim denemesi")
        await main.MainWindow.send_message.__wrapped__(window)
        after_send = displayed_rows()
        assert list(after_send) == list(range(3, 103))
        assert after_send[102].body.text() == "Gönderim denemesi"
        assert all(after_send[index] is after_receive[index] for index in range(3, 102))
        await switch_chat(102)
        assert list(displayed_rows()) == [1, 2]
        assert not opened_windows, opened_windows[:10]

    try:
        window.store.upsert_chats([
            {"peer_id": peer_id, "title": title, "kind": kind, "can_send": 1,
             "access_hash": None, "username": None, "unread_count": 0,
             "last_message": "", "last_message_at": None}
            for peer_id, title, kind in [(-101, "Grup", "Grup"), (102, "Kişi", "Kişi")]
        ])
        window.store.cache_messages(history[-101])
        window.refresh_chats()
        window.telegram = Telegram()
        asyncio.run(exercise())
    finally:
        app.removeEventFilter(watcher)
        window.telegram = None
        window.close()
