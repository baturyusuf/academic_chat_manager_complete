"""Theme, typography and conversation background."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QColorDialog, QFileDialog, QPushButton, QTreeWidgetItemIterator, QWidget

if __package__:
    from .ui_common import TREE_ICON_ROLE, _icon_size, _line_icon, _theme_stylesheet
else:  # Direct and frozen entry points
    from ui_common import TREE_ICON_ROLE, _icon_size, _line_icon, _theme_stylesheet


class AppearanceView:
    """Theme, typography and conversation background."""

    def _load_settings(self):
        self.theme.setCurrentText(self.store.preference('appearance/theme','Açık'));self.font.setCurrentText(self.store.preference('appearance/font','Segoe UI'));self.font_size.setValue(self.store.preference('appearance/font_size',13));self.density.setCurrentText(self.store.preference('appearance/density','Rahat'));self.credit_check.setChecked(self.store.preference('appearance/credit',True));self.credit.setVisible(self.credit_check.isChecked());self.bg_path.setText(self.store.preference('appearance/background',''));self.accent_btn.setText(self.store.preference('appearance/accent','#a90025'));self.apply_theme();self.apply_font();self.apply_density();self._set_message_background(self.bg_path.text())

    def _refresh_ui_icons(self):
        theme = self.theme.currentText() if hasattr(self, "theme") else "Açık"
        dark = theme == "Koyu" or (theme == "Sistem ayarı" and QApplication.palette().color(QPalette.Window).lightness() < 128)
        accent = self.store.preference("appearance/accent", "#a90025")
        text = "#e8edf5" if dark else "#202938"
        muted = "#a1adbd" if dark else "#687589"
        accent_text = "#202938" if QColor(accent).lightness() > 155 else "#ffffff"
        selected = "#ffffff" if dark else "#202938"
        size = _icon_size(self.font_size.value() if hasattr(self, "font_size") else 13)
        for button in self.findChildren(QPushButton):
            name = button.property("uiIcon")
            if not name:
                continue
            color = ("#ff9aa5" if dark else "#a61d35") if button.objectName() == "clearAttachments" else accent_text if button.property("active") or button.objectName() == "primary" else text
            button.setIcon(_line_icon(name, color, size, muted, color))
            button.setIconSize(QSize(size, size))
        if hasattr(self, "tabs"):
            self.tabs.setIconSize(QSize(size, size))
            for index, name in enumerate(("chats", "folders")):
                color = accent_text if self.active_nav == name else muted
                self.tabs.setTabIcon(index, _line_icon(name, color, size, muted, accent_text))
        if hasattr(self, "tree"):
            self.tree.setIconSize(QSize(size, size))
            iterator = QTreeWidgetItemIterator(self.tree)
            while iterator.value():
                item = iterator.value()
                name = item.data(0, TREE_ICON_ROLE)
                if name:
                    item.setIcon(0, _line_icon(name, text, size, muted, selected))
                iterator += 1
        if hasattr(self, "chat_list"):
            avatar_size = round(40 * size / 18)
            self.chat_list.setIconSize(QSize(avatar_size, avatar_size))

    def apply_theme(self,*args):
        if not hasattr(self,'theme'):return
        theme=self.theme.currentText();accent=self.store.preference('appearance/accent','#a90025')
        is_dark=theme=='Koyu' or (theme=='Sistem ayarı' and QApplication.palette().color(QPalette.Window).lightness()<128)
        self.setStyleSheet(_theme_stylesheet(is_dark,accent));self.store.set_preference('appearance/theme',theme)
        self._refresh_ui_icons()
        if hasattr(self,'messages'):self._set_message_background(self.bg_path.text() if hasattr(self,'bg_path') else '')

    def apply_font(self,*args):
        if not hasattr(self,'font_size'):return
        size=self.font_size.value();family=self.font.currentText();self.font_px.setText(f"{size} pt");f=QFont(family);f.setPointSize(size);QApplication.instance().setFont(f);self.setFont(f)
        for widget in self.findChildren(QWidget):
            widget.setFont(f);widget.updateGeometry();widget.update()
        if hasattr(self,'credit'):
            small=QFont(f);small.setPointSize(max(7,size-4));self.credit.setFont(small)
        if hasattr(self,'chat_list'):
            for i in range(self.chat_list.count()):self.chat_list.item(i).setSizeHint(QSize(0,self._chat_row_height()))
        self._refresh_ui_icons()
        if hasattr(self,'tree'):self.tree.doItemsLayout()
        self.store.set_preference('appearance/font',family);self.store.set_preference('appearance/font_size',size)
        if hasattr(self,"messages"):self.messages._sync_bubble_widths()

    def apply_density(self,*args):
        if not hasattr(self,'chat_list'):return
        spacing={'Rahat':7,'Standart':4,'Yoğun':1}.get(self.density.currentText(),4);self.chat_list.setSpacing(spacing)
        for i in range(self.chat_list.count()):self.chat_list.item(i).setSizeHint(QSize(0,self._chat_row_height()))
        self.store.set_preference('appearance/density',self.density.currentText())

    def choose_accent(self):
        c=QColorDialog.getColor(QColor(self.store.preference('appearance/accent','#a90025')),self)
        if c.isValid():self.store.set_preference('appearance/accent',c.name());self.accent_btn.setText(c.name());self.apply_theme()

    def choose_background(self):
        path,_=QFileDialog.getOpenFileName(self,"Sohbet arka planı seç","","Görseller (*.png *.jpg *.jpeg *.webp)")
        if path:self.bg_path.setText(path);self.store.set_preference('appearance/background',path);self._set_message_background(path)

    def choose_background_color(self):
        color=QColorDialog.getColor(QColor(self.store.preference('appearance/background_color','#f8f8fb')),self,"Sohbet arka plan rengini seç")
        if color.isValid():self.bg_path.clear();self.store.set_preference('appearance/background','');self.store.set_preference('appearance/background_color',color.name());self._set_message_background('')

    def clear_background(self):
        self.bg_path.clear();self.store.set_preference('appearance/background','')
        dark=self.theme.currentText()=='Koyu' or (self.theme.currentText()=='Sistem ayarı' and QApplication.palette().color(QPalette.Window).lightness()<128)
        self.store.set_preference('appearance/background_color','#171c25' if dark else '#eef1f6');self._set_message_background('')

    def _set_message_background(self,path):
        color=self.store.preference('appearance/background_color','#eef1f6' if self.theme.currentText()!='Koyu' else '#171c25') if hasattr(self,'theme') else '#eef1f6'
        if path and Path(path).is_file():
            image_url=Path(path).resolve().as_uri()
            self.messages.setStyleSheet(f"QListWidget#messages{{background-color:{color};background-image:url(\"{image_url}\");background-position:center;background-repeat:no-repeat}}")
        else:self.messages.setStyleSheet(f"QListWidget#messages{{background:{color}}}")
