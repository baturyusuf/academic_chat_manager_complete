"""Shared desktop UI constants, formatting, icons and stylesheet."""
from __future__ import annotations
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton


APP_DIR=Path(__file__).parent
TREE_NODE_KIND_ROLE=Qt.UserRole+1
TREE_OWNER_COLLECTION_ROLE=Qt.UserRole+2
TREE_ICON_ROLE=Qt.UserRole+3
NOTIFICATION_KINDS = {"Kişi": "Kişiler", "Grup": "Gruplar", "Kanal": "Kanallar", "Bot": "Botlar"}
NOTIFICATION_RULES = {
    "default": "Tür ayarını kullan",
    "all": "Tüm mesajlar",
    "mentions": "Yalnızca benden bahsedilince",
    "priority": "Önemli bildirim",
    "off": "Sessiz",
}
NOTIFICATION_SCOPES = (
    "Tüm bildirimler", "Yalnızca koleksiyonlar", "Yalnızca önemli sohbetler", "Sessiz mod",
)
MENTION_KINDS = ("Grup", "Kanal")
COLLECTION_ICON_OPTIONS="""📁 📂 🗂️ 🗃️ 🗄️ 📌 📍 🏷️ 🎓 🏫 📚 📖 📝 ✏️ 📎 📋 💼 🧑‍🏫 👨‍🏫 👩‍🏫 👨‍🎓 👩‍🎓 🧑‍🎓 🧠 💻 🖥️ ⌨️ 🖱️ 📱 🌐 🔬 🧪 🧬 🧫 🩺 💊 🏥 ⚙️ 🔧 🛠️ 🧰 🧮 📊 📈 📉 🗓️ 📅 ⏰ ⏳ ✅ ☑️ ✔️ ❌ ❗ ❓ ⚠️ ⭐ 🌟 ✨ 🔥 💡 🎯 🏆 🥇 🏅 🎨 🎭 🎵 🎼 🎬 📷 🖼️ 🎥 🎤 🎧 🎹 🎸 ⚽ 🏀 🏐 🎾 🏓 🏸 🏊 🏃 🚴 🧘 🍎 🍕 ☕ 🍰 🌱 🌳 🌻 🌍 🌈 ☀️ 🌙 ⛅ ❄️ ❤️ 💙 💚 💛 💜 🤍 🖤 👥 👤 🧑‍🤝‍🧑 👪 🏠 🏢 🏛️ 🚀 ✈️ 🚗 🚆 💰 💳 🛒 🎁 🧳 🔑 🔒 🔔 📣 📢 💬 📨 📩 ✉️""".split()
COLLECTION_ICON_OPTIONS += """🗒️ 📃 📄 📑 🧾 🗞️ 📇 📈 📉 📊 🗃️ 📁 📂 🗂️ 🗄️ 🗑️ 🔖 🏷️ 🔗 🧷 🧵 🪡 🧶 🪢 🪣 🧹 🧺 🪟 🪞 🛋️ 🛏️ 🪑 🚪 🪜 🧯 🛒 🧰 🪛 🪚 🔨 ⚒️ ⚙️ 🪤 🧲 🪝 🧪 🧫 🧬 🔭 🔬 🩻 🩹 🩺 🧴 🧼 🪥 🧽 🧹 🧻 🛟 🧑‍🔬 👩‍🔬 👨‍🔬 🧑‍💻 👩‍💻 👨‍💻 🧑‍🏫 👩‍🏫 👨‍🏫 🧑‍🎓 👩‍🎓 👨‍🎓 🧑‍⚕️ 👩‍⚕️ 👨‍⚕️ 🧑‍🚀 👩‍🚀 👨‍🚀 🧑‍⚖️ 👩‍⚖️ 👨‍⚖️ 🧑‍🔧 👩‍🔧 👨‍🔧 🧑‍🍳 👩‍🍳 👨‍🍳 🧑‍🎨 👩‍🎨 👨‍🎨 🧑‍🚒 👩‍🚒 👨‍🚒 🧑‍✈️ 👩‍✈️ 👨‍✈️ 👥 🫂 🗣️ 👤 👪 🧑‍🤝‍🧑 👭 👫 👬 🧑‍🧑‍🧒‍🧒 🏛️ 🏢 🏫 🏥 🏦 🏭 🏬 🏟️ 🏖️ 🏕️ 🏠 🏡 🏘️ 🏚️ 🏗️ ⛪ 🕌 🛕 🕍 ⛩️ 🕋 🎓 🎒 🧳 🌍 🌎 🌏 🗺️ 🧭 🧱 🛣️ 🚦 🚥 🛤️ 🚉 🚇 🚊 🚍 🚘 🚲 🛴 🛵 🚗 🚕 🚙 🚌 🚎 🚐 🚑 🚒 🚓 🚔 🚚 🚛 🚜 🚄 🚅 🚆 🚇 🚈 🚉 ✈️ 🛫 🛬 🚀 🛸 🛰️ ⛵ 🚤 🛥️ 🚢 ⚓ 🌐 🕸️ 📡 🛜 🔋 🔌 🪫 💻 🖥️ 🖨️ ⌨️ 🖱️ 🖲️ 💽 💾 💿 📀 📼 📱 📲 ☎️ 📞 📟 📠 🔍 🔎 💡 🔦 🕯️ 🪔 🧯 🛢️ 💸 💵 💴 💶 💷 💰 🪙 💳 🧮 📉 📈 📊 🧾 ⚖️ 🪙 🏆 🏅 🥇 🥈 🥉 🎖️ 🏵️ 🎗️ 🎟️ 🎫 🎪 🎭 🩰 🎨 🖌️ 🖍️ 🧵 🪡 🎼 🎵 🎶 🎤 🎧 🎹 🥁 🎷 🎺 🎸 🪕 🎻 🎬 🎥 📽️ 🎞️ 📸 📷 📹 📺 📻 🎙️ 🎚️ 🎛️ 🧩 ♟️ 🎯 🎮 🕹️ 🎲 🃏 🀄 🧸 🪅 🪩 🎉 🎊 🎈 🎁 🎀 🪄 🪅 🧿 💎 🪬 🛡️ ⚔️ 🔮 🪄 🪷 🌸 🌼 🌻 🌷 🪻 🌱 🪴 🌲 🌳 🌴 🌵 🍀 ☘️ 🍁 🍂 🍃 🌾 🌿 🪹 🪺 🪨 🌊 🔥 💧 ☔ 🌈 ☀️ 🌤️ ⛅ 🌥️ ☁️ 🌦️ 🌧️ ⛈️ 🌩️ 🌨️ ❄️ ☃️ ⛄ 🌬️ 🌪️ 🌫️ 🌙 🌛 🌜 🌝 🌚 ⭐ 🌟 ✨ 💫 🌠 🌌 🪐 🌍 🌎 🌏 🌑 🌒 🌓 🌔 🌕 🌖 🌗 🌘 🍎 🍏 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🥦 🥬 🥒 🌶️ 🫑 🌽 🥕 🫒 🧄 🧅 🥔 🍠 🥐 🥯 🍞 🥖 🧀 🥚 🍳 🥞 🧇 🥓 🥩 🍗 🍖 🌭 🍔 🍟 🍕 🫓 🥪 🥙 🧆 🌮 🌯 🫔 🥗 🥘 🫕 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🦪 🍤 🍙 🍚 🍘 🍥 🥠 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 🌰 🥜 🫘 🍯 🥛 🍼 ☕ 🫖 🍵 🧃 🥤 🧋 🍶 🍺 🍻 🥂 🍷 🥃 🍸 🍹 🧉 🍾 😃 😄 😁 😆 😅 😂 🤣 🥲 🥹 ☺️ 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🫢 🫣 🤫 🤔 🫡 🤐 🤨 😐 😑 😶 🫥 😏 😒 🙄 😬 🤥 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🤧 🥵 🥶 🥴 😵 🤯 🤠 🥳 🥸 😎 🤓 🧐 😕 🫤 😟 🙁 ☹️ 😮 😯 😲 😳 🥺 🥹 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 ☠️ 💩 🤡 👻 👽 👾 🤖 🎃 😺 😸 😹 😻 😼 😽 🙀 😿 😾 🙈 🙉 🙊 💌 💘 💝 💖 💗 💓 💞 💕 💟 ❣️ 💔 ❤️‍🔥 ❤️‍🩹 ❤️ 🩷 🧡 💛 💚 💙 🩵 💜 🤎 🖤 🩶 🤍 💯 💢 💥 💫 💦 💨 🕳️ 💬 👁️‍🗨️ 🗨️ 🗯️ 💭 💤 👋 🤚 🖐️ ✋ 🖖 🫱 🫲 🫳 🫴 🫰 🫵 🫶 🤌 🤏 ✌️ 🤞 🫰 🤟 🤘 🤙 👈 👉 👆 🖕 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 🫶 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 🦿 🦵 🦶 👂 🦻 👃 🧠 🫀 🫁 🦷 🦴 👀 👁️ 👅 👄 🫦 🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐻‍❄️ 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🐔 🐧 🐦 🐤 🦆 🦅 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🪱 🐛 🦋 🐌 🐞 🐜 🪰 🪲 🪳 🦟 🦗 🕷️ 🦂 🐢 🐍 🦎 🦖 🦕 🐙 🦑 🦐 🦞 🦀 🐡 🐠 🐟 🐬 🐳 🦈 🐊 🐅 🐆 🦓 🦍 🦧 🐘 🦛 🦏 🐪 🐫 🦒 🦘 🦬 🐃 🐂 🐄 🐎 🐖 🐏 🐑 🦙 🐐 🦌 🐕 🦮 🐕‍🦺 🐩 🐈 🐈‍⬛ 🪶 🐓 🦃 🦤 🦚 🦜 🪽 🐇 🦝 🦨 🦡 🦫 🦦 🦥 🐁 🐀 🐿️ 🦔 🐾 🐉 🐲 🌵 🎄 🌲 🌳 🌴 🪵 🌱 🌿 ☘️ 🍀 🎍 🪴 🎋 🍃 🍂 🍁 🪺 🪻 🥀 🌺 🌸 🌼 🌷 🪷 🌹 🪸 🪷 🏵️""".split()
COLLECTION_ICON_OPTIONS=list(dict.fromkeys(COLLECTION_ICON_OPTIONS))
def _mix_color(foreground: str, background: str, amount: float) -> str:
    fg, bg = QColor(foreground), QColor(background)
    channels = [round(bg.getRgb()[i] * (1 - amount) + fg.getRgb()[i] * amount) for i in range(3)]
    return QColor(*channels).name()

# Original 24-unit line icons, rendered as DPI-aware Qt pixmaps.
_ICON_PATHS = {
    "chats": "M4 4H20V16H10L4 21Z",
    "folders": "M3 6H10L12 8H21V19H3Z",
    "bulk": "M3 4L21 12L3 20L7 12L3 4ZM7 12H21",
    "history": "M12 3A9 9 0 1 1 3 12A9 9 0 0 1 12 3ZM12 7V12L16 15",
    "filters": "M3 4H21L14 12V19L10 21V12Z",
    "notifications": "M5 17H19L17 14V9A5 5 0 0 0 7 9V14ZM10 21H14",
    "settings": "M4 6H20M4 12H20M4 18H20M8 3V9M16 9V15M10 15V21",
    "plus": "M12 4V20M4 12H20",
    "up": "M12 20V4M5 11L12 4L19 11",
    "close": "M6 6L18 18M18 6L6 18",
    "attach": "M8 13L14 7A3 3 0 0 1 18 11L10 19A5 5 0 0 1 3 12L13 2M8 13A1 1 0 0 0 10 15L16 9",
    "emoji": "M12 3A9 9 0 1 1 3 12A9 9 0 0 1 12 3ZM8 9H8.1M16 9H16.1M8 14Q12 18 16 14",
    "refresh": "M20 10A8 8 0 1 0 19 17M20 3V10H13",
    "image": "M3 4H21V20H3ZM3 16L9 10L15 16L18 13L21 16M16 8H16.1",
    "copy": "M8 8H21V21H8ZM16 8V3H3V16H8",
    "reply": "M10 5L3 12L10 19M3 12H15Q21 12 21 19",
    "download": "M12 3V15M6 9L12 15L18 9M4 16V21H20V16",
    "edit": "M4 20L5 14L16 3L21 8L10 19ZM14 5L19 10",
    "trash": "M3 6H21M9 6V3H15V6M6 6L7 21H17L18 6M10 10V17M14 10V17",
    "check": "M4 12L10 18L20 6",
    "eye": "M2 12Q12 -1 22 12Q12 25 2 12ZM12 9A3 3 0 1 1 9 12A3 3 0 0 1 12 9",
    "eye-off": "M3 3L21 21M2 12Q5 7 8 6M11 5Q17 4 22 12Q20 15 17 17M13 19Q7 20 2 12",
    "person": "M12 12A4 4 0 1 0 12 4A4 4 0 0 0 12 12ZM4 21A8 8 0 0 1 20 21",
    "group": "M16 21A6 6 0 0 0 4 21M10 11A4 4 0 1 0 10 3A4 4 0 0 0 10 11ZM16 4A4 4 0 0 1 16 12M18 15A6 6 0 0 1 22 21",
    "panel": "M3 4H21V20H3ZM9 4V20M12 8H17M12 12H17",
    "down": "M12 4V20M5 13L12 20L19 13",
}

def _icon_size(font_size):
    return max(16, min(28, round(font_size * 18 / 13)))

@lru_cache(maxsize=256)
def _line_icon(name, color, size, disabled_color, selected_color):
    icon = QIcon()
    for mode, stroke in ((QIcon.Normal, color), (QIcon.Active, color),
                         (QIcon.Disabled, disabled_color), (QIcon.Selected, selected_color)):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="{_ICON_PATHS[name]}" fill="none" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        for scale in (1, 2, 3):
            pixmap = QPixmap(size * scale, size * scale)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            pixmap.setDevicePixelRatio(scale)
            icon.addPixmap(pixmap, mode)
    return icon

def _icon_button(name, text="", tooltip=""):
    button = QPushButton(text)
    button.setProperty("uiIcon", name)
    if tooltip:
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
    if not text:
        button.setObjectName("iconOnly")
    return button

def _local_datetime(value):
    """Parse Telegram/SQLite UTC timestamps and convert them to the computer's zone."""
    if not value:return None
    try:
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone()
    except (TypeError,ValueError):return None

def _format_local_datetime(value,fmt="%Y-%m-%d %H:%M:%S"):
    parsed=_local_datetime(value)
    return parsed.strftime(fmt) if parsed else str(value or "")

def _format_chat_datetime(value):
    parsed=_local_datetime(value)
    if not parsed:return ""
    now=datetime.now().astimezone()
    return parsed.strftime("%H:%M" if parsed.date()==now.date() else "%d.%m.%Y")

def _theme_stylesheet(dark: bool, accent: str) -> str:
    highlight = _mix_color(accent, "#ffffff", .42) if dark else accent
    accent_text = "#202938" if QColor(accent).lightness() > 155 else "#ffffff"
    if dark:
        c = dict(window="#151922", surface="#1d232e", raised="#252c38", input="#202733",
                 text="#e8edf5", muted="#a1adbd", border="#343d4c", hover="#2b3442",
                 selection=_mix_color(accent, "#252c38", .28), selected_text="#ffffff",
                 track="#343d4c", status="#1d232e")
    else:
        c = dict(window="#f3f5f9", surface="#ffffff", raised="#f7f8fb", input="#f7f8fb",
                 text="#202938", muted="#687589", border="#e2e7ef", hover="#eef1f6",
                 selection=_mix_color(accent, "#ffffff", .13), selected_text="#202938",
                 track="#e2e7ef", status="#ffffff")
    danger = "#ff9aa5" if dark else "#a61d35"
    danger_hover = _mix_color(danger, c['surface'], .12)
    danger_pressed = _mix_color(danger, c['surface'], .22)
    return f"""
    QMainWindow,QWidget#root{{background:{c['window']};color:{c['text']}}}
    QWidget{{color:{c['text']}}}
    QFrame#topbar,QFrame#sidebar,QFrame#panel,QFrame#conversation,QFrame#compose{{background:{c['surface']};border:1px solid {c['border']};border-radius:14px}}
    QDialog,QMessageBox,QInputDialog{{background:{c['surface']};color:{c['text']}}}
    QDialog QLabel,QMessageBox QLabel,QInputDialog QLabel{{color:{c['text']}}}
    QDialogButtonBox QPushButton{{min-width:74px}}
    QStackedWidget#centerStack{{background:transparent}}
    QScrollArea#settingsPage,QScrollArea#settingsPage QWidget#qt_scrollarea_viewport,QWidget#settingsInner{{background:{c['surface']}}}
    QFrame#chatHeader{{background:{c['surface']};border:0;border-bottom:1px solid {c['border']};border-top-left-radius:14px;border-top-right-radius:14px}}
    QFrame#replyPreviewFrame{{background:{c['raised']};border-left:3px solid {accent};border-radius:7px}}
    QFrame#notificationBanner{{background:{c['raised']};border-left:3px solid {accent};border-radius:7px}}
    QLabel#brandTitle,QLabel#sectionTitle{{font-weight:700;color:{c['text']}}}
    QLabel#brandSubtitle,QLabel#muted{{color:{c['muted']}}}
    QPushButton{{border:0;border-radius:9px;background:transparent;padding:8px 11px;text-align:left;color:{c['text']}}}
    QPushButton:hover{{background:{c['hover']}}}
    QPushButton#iconOnly{{text-align:center;padding:7px;border:1px solid transparent}}
    QPushButton#iconOnly:focus{{border-color:{highlight}}}
    QPushButton[active="true"],QPushButton#primary,QPushButton#primary:checked{{background:{accent};color:{accent_text};font-weight:600}}
    QPushButton#primary:hover{{background:{_mix_color(accent, '#000000' if dark else '#ffffff', .88)}}}
    QPushButton#clearAttachments{{background:transparent;color:{danger};border:1px solid {_mix_color(danger, c['border'], .55)};border-radius:9px;padding:7px 10px;text-align:center;font-weight:600}}
    QPushButton#clearAttachments:hover{{background:{danger_hover};border-color:{danger}}}
    QPushButton#clearAttachments:pressed{{background:{danger_pressed};border-color:{danger}}}
    QPushButton#clearAttachments:focus{{border-color:{danger}}}
    QPushButton#clearAttachments:disabled{{background:transparent;color:{c['muted']};border-color:{c['border']}}}
    QLineEdit,QComboBox,QSpinBox,QPlainTextEdit{{background:{c['input']};color:{c['text']};border:1px solid {c['border']};border-radius:10px;padding:8px 10px;selection-background-color:{accent};selection-color:#ffffff}}
    QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus{{border:1px solid {accent}}}
    QListWidget,QTreeWidget,QTableWidget{{border:0;background:transparent;color:{c['text']};outline:0;alternate-background-color:{c['raised']}}}
    QListWidget::item{{padding:9px 8px;border-bottom:1px solid {c['border']};border-radius:8px}}
    QListWidget::item:selected,QTreeWidget::item:selected,QTableWidget::item:selected{{background:{c['selection']};color:{c['selected_text']}}}
    QTreeWidget::item{{padding:5px}}
    QGroupBox{{background:{c['surface']};border:1px solid {c['border']};border-radius:12px;margin-top:14px;padding:14px 12px 12px;font-weight:650}}
    QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 4px;color:{c['text']}}}
    QHeaderView,QHeaderView::viewport{{background:{c['raised']};color:{c['text']}}}
    QHeaderView::section{{background:{c['raised']};color:{c['text']};border:0;border-bottom:1px solid {c['border']};padding:7px 9px;font-weight:600}}
    QTableCornerButton::section{{background:{c['raised']};border:0}}
    QSlider::groove:horizontal{{height:5px;background:{c['track']};border-radius:2px}}
    QSlider::handle:horizontal{{background:{accent};width:15px;margin:-5px 0;border-radius:7px}}
    QTabWidget::pane{{border:0}}
    QTabBar::tab{{background:{c['raised']};color:{c['muted']};padding:10px 16px;border-radius:9px 9px 0 0;margin-right:4px}}
    QTabBar::tab:selected{{background:{accent};color:{accent_text};font-weight:600}}
    QSplitter::handle{{background:{c['border']};width:5px;margin:0 2px;border-radius:2px}}
    QSplitter::handle:hover{{background:{accent}}}
    QStatusBar{{background:{c['status']};color:{c['muted']};border-top:1px solid {c['border']}}}
    QMenu{{background:{c['surface']};color:{c['text']};border:1px solid {c['border']};padding:4px}}
    QMenu::item{{padding:7px 22px;border-radius:5px}}
    QMenu::item:selected{{background:{c['selection']};color:{c['selected_text']}}}
    QMenu#messageContextMenu{{padding:6px;border-radius:9px}}
    QMenu#messageContextMenu::item{{padding:9px 26px 9px 34px;border-radius:6px}}
    QMenu#messageContextMenu::separator{{height:1px;background:{c['border']};margin:5px 8px}}
    QFrame#attachmentCard{{background:{c['raised']};border:1px solid {c['border']};border-radius:8px}}
    QLabel#attachmentName{{font-weight:600}}
    QPushButton#attachmentDownload{{text-align:center;color:{highlight};border:1px solid {c['border']};padding:6px 9px}}
    QPushButton#attachmentDownload:disabled{{color:{c['muted']}}}
    QFrame#outgoingBubble{{background:{'#2b5278' if dark else '#e6f3ff'};border:0;border-radius:13px}}
    QFrame#incomingBubble{{background:{'#182533' if dark else '#ffffff'};border:0;border-radius:13px}}
    QLabel#messageSender{{font-weight:650;color:{highlight}}}
    QLabel#messageText{{color:{c['text']}}}
    QLabel#messageTime{{color:{c['muted']}}}
    QLabel#messageTicks{{color:{'#8fc4fa' if dark else '#4e86d6'};font-weight:700}}
    QLabel#senderAvatar{{border-radius:16px}}
    QLabel#imagePreview{{background:#10151c;color:{c['muted']};border-radius:9px}}
    QLabel#reactionSummary{{color:{c['muted']};padding:3px 0}}
    QLabel#replyQuote{{background:{c['raised']};border-left:3px solid {accent};border-radius:5px;padding:5px 8px;color:{c['muted']}}}
    QListWidget#messages::item{{border:0;background:transparent;padding:0}}
    QScrollBar:vertical{{background:transparent;width:10px;margin:3px}}
    QScrollBar::handle:vertical{{background:{c['border']};border-radius:5px;min-height:30px}}
    QScrollBar::handle:vertical:hover{{background:{c['muted']}}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0}}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical,QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{{background:transparent}}
    QScrollBar:horizontal{{background:transparent;height:10px;margin:3px}}
    QScrollBar::handle:horizontal{{background:{c['border']};border-radius:5px;min-width:30px}}
    QScrollBar::handle:horizontal:hover{{background:{c['muted']}}}
    QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0}}
    """
