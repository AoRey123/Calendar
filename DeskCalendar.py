# -*- coding: utf-8 -*-
"""
Настольный календарь со списком дел.
Запуск: python desk_calendar.py   (или pythonw desk_calendar.py без чёрного окна)

- окно без рамки, перетаскивается за верхнюю полосу
- размер меняется за правый нижний уголок
- держится на рабочем столе под остальными окнами и не сворачивается по Win+D
- на каждый день можно добавить список дел с галочками
- дни с делами подсвечены; если все дела дня выполнены, день краснеет
- данные хранятся в %APPDATA%\\DeskCalendar\\data.json и не пропадают
"""

import sys
import os
import json
import shutil
import ctypes
from ctypes import wintypes

from PySide6.QtCore import (
    Qt, QDate, QTimer, QLocale, Signal, QPointF, QRectF, QEvent,
)
from PySide6.QtGui import (
    QTextCharFormat, QColor, QFont, QIcon, QPalette, QShortcut, QKeySequence,
    QPainter, QPen, QPolygonF, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QCalendarWidget, QLabel, QPushButton, QSizeGrip, QToolButton,
    QAbstractItemView, QListWidget, QListWidgetItem, QLineEdit,
    QTextEdit,
)

DATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "DeskCalendar"
)
DATA_FILE = os.path.join(DATA_DIR, "data.json")
BACKUP_FILE = os.path.join(DATA_DIR, "data_backup.json")

# ---------- WinAPI: не даём окну свернуться по Win+D ----------
user32 = None
if sys.platform == "win32":
    try:
        user32 = ctypes.windll.user32
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.UINT,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
    except Exception:
        user32 = None

SW_SHOWNOACTIVATE = 4
HWND_TOP = 0
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010

# ---------- палитра (груша / томат / мёд / шалфей) ----------
PANEL = "#F6CE98"        # Honey: фон панели
GRID = "#FBE5C2"         # светлый мёд: сетка календаря и список дел
TOMATO = "#BA5126"       # Tomato: шапка с месяцем, выходные, выполненные дни
HEADER_ROW = "#8EA473"   # Sage: строка с днями недели
NOTE_BG = "#8EA473"      # Sage: дни с невыполненными делами
DONE_BG = "#BA5126"      # цвет дня, где все дела выполнены
SELECT_BG = "#F79C2B"    # Pear: выбранный день
SELECT_TEXT = "#2E2410"  # текст на выбранном дне
TEXT = "#3F4A2E"         # тёмный шалфей: основной текст
NAV_TEXT = "#FBE5C2"     # текст на шапке с месяцем и на выполненных днях
MUTED = "#9A7B55"        # второстепенный текст, выполненные дела в списке
WEEKEND = TOMATO         # цвет выходных
OTHER_MONTH = "#BDA27B"  # дни соседних месяцев
TODAY_BORDER = "#3F4A2E" # рамка вокруг сегодняшней даты
NOTES_W = 240            # ширина боковой панели заметок
NOTES_GAP = 8            # зазор между календарём и панелью заметок
WATER_GLASSES = 8        # сколько стаканов воды в день (можно поставить 9)
WATER = "#7FB2C4"        # вода в стакане
WATER_EDGE = "#4F8197"   # контур наполненного стакана

STYLE = f"""
#panel {{
    background-color: rgba(246, 206, 152, 245);
    border-radius: 14px;
}}
QLabel#title {{ color: {TEXT}; font-size: 14px; font-weight: bold; }}
QPushButton#close {{
    background: transparent; color: {MUTED}; border: none;
    font-size: 16px; padding: 2px 8px;
}}
QPushButton#notesbtn, QPushButton#pinbtn {{
    background: transparent; border: none; font-size: 15px;
    padding: 2px 8px; border-radius: 6px;
}}
QPushButton#notesbtn:hover, QPushButton#pinbtn:hover {{ background: {GRID}; }}
QPushButton#notesbtn:checked, QPushButton#pinbtn:checked {{ background: {GRID}; }}
QLabel#waterlabel {{ color: {TEXT}; font-size: 13px; font-weight: bold; }}
QPushButton#close:hover {{ color: {NAV_TEXT}; background: {TOMATO}; border-radius: 6px; }}

QCalendarWidget {{ background-color: {GRID}; }}
QCalendarWidget #qt_calendar_navigationbar {{
    background-color: {TOMATO};
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QCalendarWidget QToolButton {{
    color: {NAV_TEXT}; background: transparent; font-size: 15px;
    border: none; padding: 4px 10px;
}}
QCalendarWidget QToolButton:hover {{
    background: {SELECT_BG}; color: {SELECT_TEXT}; border-radius: 6px;
}}
QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
QCalendarWidget QMenu {{ background: {PANEL}; color: {TEXT}; }}
QCalendarWidget QSpinBox {{ background: {GRID}; color: {TEXT}; }}

QCalendarWidget QAbstractItemView:enabled {{
    background-color: {GRID};
    alternate-background-color: {HEADER_ROW};
    color: {TEXT};
    font-size: 13px;
    selection-background-color: {SELECT_BG};
    selection-color: {SELECT_TEXT};
    outline: 0;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {OTHER_MONTH}; }}

QListWidget {{
    background-color: {GRID};
    color: {TEXT};
    border: 1px solid {NOTE_BG};
    border-radius: 8px; padding: 4px; font-size: 13px; outline: 0;
}}
QListWidget::item {{ padding: 4px 2px; }}
QListWidget::item:selected {{ background: {PANEL}; color: {TEXT}; }}
QListWidget::indicator {{
    width: 16px; height: 16px; border: 2px solid {TOMATO};
    border-radius: 5px; background: {GRID};
}}
QListWidget::indicator:checked {{ background: {TOMATO}; }}

QTextEdit {{
    background-color: {GRID}; color: {TEXT};
    border: 1px solid {NOTE_BG}; border-radius: 8px;
    padding: 6px; font-size: 13px;
}}

QLineEdit {{
    background-color: {GRID}; color: {TEXT};
    border: 1px solid {NOTE_BG}; border-radius: 8px;
    padding: 5px 8px; font-size: 13px;
}}
QPushButton#add {{
    background: {TOMATO}; color: {NAV_TEXT}; border: none;
    border-radius: 8px; padding: 4px 12px; font-size: 16px; font-weight: bold;
}}
QPushButton#add:hover {{ background: {SELECT_BG}; color: {SELECT_TEXT}; }}
QPushButton#del {{
    background: transparent; color: {MUTED}; border: 1px solid {NOTE_BG};
    border-radius: 8px; padding: 4px 8px; font-size: 14px;
}}
QPushButton#del:hover {{ background: {GRID}; color: {TOMATO}; }}
"""


def draw_icon_pixmap(size):
    """Иконка календаря в цветах палитры, рисуется кодом."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    u = size / 100.0
    p.setPen(Qt.NoPen)
    # корпус
    p.setBrush(QColor(GRID))
    p.drawRoundedRect(QRectF(8 * u, 14 * u, 84 * u, 78 * u), 14 * u, 14 * u)
    # верхняя полоса (томатная)
    p.setBrush(QColor(TOMATO))
    p.drawRoundedRect(QRectF(8 * u, 14 * u, 84 * u, 28 * u), 14 * u, 14 * u)
    p.drawRect(QRectF(8 * u, 28 * u, 84 * u, 14 * u))
    # кольца
    p.setBrush(QColor(TEXT))
    for x in (30, 70):
        p.drawRoundedRect(QRectF((x - 4) * u, 6 * u, 8 * u, 18 * u), 4 * u, 4 * u)
    # выбранный день (груша) и день с делами (шалфей)
    p.setBrush(QColor(SELECT_BG))
    p.drawRoundedRect(QRectF(22 * u, 54 * u, 22 * u, 22 * u), 5 * u, 5 * u)
    p.setBrush(QColor(NOTE_BG))
    p.drawRoundedRect(QRectF(56 * u, 54 * u, 22 * u, 22 * u), 5 * u, 5 * u)
    p.end()
    return pm


def make_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_icon_pixmap(size))
    return icon


def save_icon_file():
    """Положить icon.ico рядом с данными (пригодится для ярлыка)."""
    path = os.path.join(DATA_DIR, "icon.ico")
    if os.path.exists(path):
        return
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        draw_icon_pixmap(256).save(path, "ICO")
    except Exception:
        pass


class TodayCalendar(QCalendarWidget):
    """Календарь: сегодняшняя дата в рамке, выбранная дата яркой плашкой."""

    def paintCell(self, painter, rect, date):
        if date == self.selectedDate():
            # выбранный день рисуем сами: яркая заливка и жирная цифра,
            # чтобы его было видно сразу
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(SELECT_BG))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 7, 7)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(SELECT_TEXT))
            painter.drawText(rect, Qt.AlignCenter, str(date.day()))
            painter.restore()
        else:
            super().paintCell(painter, rect, date)

        if date == QDate.currentDate():
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(TODAY_BORDER))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
            painter.restore()


class WaterBar(QWidget):
    """Ряд стаканов. Клик по n-му стакану = «выпито n стаканов».
    Повторный клик по последнему наполненному стакану убирает его."""
    changed = Signal(int)

    def __init__(self, total=WATER_GLASSES):
        super().__init__()
        self.total = total
        self.count = 0
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Кликните по стакану, чтобы отметить выпитое")

    def set_count(self, n):
        self.count = max(0, min(self.total, n))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cell = self.width() / self.total
        gw = min(cell * 0.72, 24.0)
        top, bottom = 3.0, self.height() - 3.0
        inset = gw * 0.16
        for i in range(self.total):
            cx = cell * i + cell / 2
            x0, x1 = cx - gw / 2, cx + gw / 2
            glass = QPolygonF([
                QPointF(x0, top), QPointF(x1, top),
                QPointF(x1 - inset, bottom), QPointF(x0 + inset, bottom),
            ])
            filled = i < self.count
            p.setPen(QPen(QColor(WATER_EDGE if filled else MUTED), 1.6))
            p.setBrush(QColor(WATER if filled else GRID))
            p.drawPolygon(glass)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        idx = int(event.position().x() // (self.width() / self.total)) + 1
        idx = max(1, min(self.total, idx))
        self.set_count(idx - 1 if idx == self.count else idx)
        self.changed.emit(self.count)


class DeskCalendar(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks = {}  # {"2026-10-18": [{"text": "...", "done": False}, ...]}
        self.drag_offset = None
        self.notes_is_open = False
        self.pinned = False
        self.water = {}  # {"2026-10-18": 5}
        self.current = QDate.currentDate()
        self.last_today = QDate.currentDate()

        self.setWindowFlags(
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Мой календарь")
        self.setWindowIcon(make_icon())
        self.setStyleSheet(STYLE)
        self.setMinimumSize(300, 440)
        self.resize(360, 600)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self.save_data)

        # «сторож»: возвращает окно, если его свернули (Win+D)
        self.guard_timer = QTimer(self)
        self.guard_timer.setInterval(300)
        self.guard_timer.timeout.connect(self.keep_on_desktop)
        self.guard_timer.start()

        self.build_ui()
        self.load_data()

        self.cal.setSelectedDate(self.current)
        self.show_tasks_for(self.current)
        self.refresh_highlights()

    # ---------- интерфейс ----------
    def build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(NOTES_GAP)

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(300)
        outer.addWidget(panel, 1)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # верхняя полоса (за неё окно таскается)
        header = QHBoxLayout()
        self.title = QLabel("Календарь")
        self.title.setObjectName("title")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setObjectName("pinbtn")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setToolTip("Закрепить поверх всех окон")
        self.pin_btn.clicked.connect(lambda checked: self.set_pinned(checked))
        self.notes_btn = QPushButton("📝")
        self.notes_btn.setObjectName("notesbtn")
        self.notes_btn.setCheckable(True)
        self.notes_btn.setCursor(Qt.PointingHandCursor)
        self.notes_btn.setToolTip("Заметки")
        self.notes_btn.clicked.connect(
            lambda checked: self.set_notes_open(checked))
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.pin_btn)
        header.addWidget(self.notes_btn)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # календарь
        self.cal = TodayCalendar()
        self.cal.setLocale(QLocale(QLocale.Russian))
        self.cal.setFirstDayOfWeek(Qt.Monday)
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.cal.selectionChanged.connect(self.on_date_changed)
        self.style_calendar()
        layout.addWidget(self.cal, 3)

        # трекер воды
        water_row = QHBoxLayout()
        water_row.setSpacing(8)
        self.water_bar = WaterBar()
        self.water_bar.changed.connect(self.on_water_changed)
        self.water_label = QLabel()
        self.water_label.setObjectName("waterlabel")
        water_row.addWidget(QLabel("💧"))
        water_row.addWidget(self.water_bar, 1)
        water_row.addWidget(self.water_label)
        layout.addLayout(water_row)

        # список дел с галочками
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setWordWrap(True)
        self.list.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.list, 2)

        # Delete удаляет выбранное дело
        sc = QShortcut(QKeySequence(Qt.Key_Delete), self.list)
        sc.setContext(Qt.WidgetShortcut)
        sc.activated.connect(self.delete_selected)

        # строка добавления нового дела
        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Новое дело, Enter — добавить")
        pal = self.input.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
        self.input.setPalette(pal)
        self.input.returnPressed.connect(self.add_task)
        add_btn = QPushButton("+")
        add_btn.setObjectName("add")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_task)
        del_btn = QPushButton("🗑")
        del_btn.setObjectName("del")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setToolTip("Удалить выбранное дело (Del)")
        del_btn.clicked.connect(self.delete_selected)
        add_row.addWidget(self.input, 1)
        add_row.addWidget(add_btn)
        add_row.addWidget(del_btn)
        layout.addLayout(add_row)

        # уголок для изменения размера (виден, пока панель заметок закрыта)
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.grip_main = QSizeGrip(self)
        bottom.addWidget(self.grip_main)
        layout.addLayout(bottom)

        # боковая панель заметок (не привязаны к датам), по умолчанию скрыта
        self.notes_panel = QFrame()
        self.notes_panel.setObjectName("panel")
        self.notes_panel.setFixedWidth(NOTES_W)
        nlay = QVBoxLayout(self.notes_panel)
        nlay.setContentsMargins(12, 8, 12, 8)
        nlay.setSpacing(8)

        ntitle = QLabel("Заметки")
        ntitle.setObjectName("title")
        nlay.addWidget(ntitle)

        self.free_notes = QTextEdit()
        self.free_notes.setAcceptRichText(False)
        self.free_notes.setPlaceholderText("Заметки без привязки к дате...")
        npal = self.free_notes.palette()
        npal.setColor(QPalette.PlaceholderText, QColor(MUTED))
        self.free_notes.setPalette(npal)
        self.free_notes.textChanged.connect(lambda: self.save_timer.start())
        nlay.addWidget(self.free_notes, 1)

        nbottom = QHBoxLayout()
        nbottom.addStretch()
        nbottom.addWidget(QSizeGrip(self))
        nlay.addLayout(nbottom)

        outer.addWidget(self.notes_panel)
        self.notes_panel.hide()

    def style_calendar(self):
        # стрелки переключения месяцев: тёмные иконки по умолчанию
        # на цветной шапке не видны, поэтому заменяем их текстом
        for name, text in (("qt_calendar_prevmonth", "‹"),
                           ("qt_calendar_nextmonth", "›")):
            btn = self.cal.findChild(QToolButton, name)
            if btn:
                btn.setIcon(QIcon())
                btn.setText(text)
                btn.setToolButtonStyle(Qt.ToolButtonTextOnly)

        # цвета выделения и фона сетки (дублируем палитрой для надёжности)
        view = self.cal.findChild(QAbstractItemView, "qt_calendar_calendarview")
        if view:
            pal = view.palette()
            pal.setColor(QPalette.Base, QColor(GRID))
            pal.setColor(QPalette.AlternateBase, QColor(HEADER_ROW))
            pal.setColor(QPalette.Highlight, QColor(SELECT_BG))
            pal.setColor(QPalette.HighlightedText, QColor(SELECT_TEXT))
            view.setPalette(pal)

        # подписи дней недели
        head = QTextCharFormat()
        head.setForeground(QColor(TEXT))
        head.setFontWeight(QFont.Bold)
        self.cal.setHeaderTextFormat(head)

        # цвет будних дней и выходных
        week = QTextCharFormat()
        week.setForeground(QColor(TEXT))
        weekend = QTextCharFormat()
        weekend.setForeground(QColor(WEEKEND))
        for d in (Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday):
            self.cal.setWeekdayTextFormat(d, week)
        for d in (Qt.Saturday, Qt.Sunday):
            self.cal.setWeekdayTextFormat(d, weekend)

    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == QEvent.ActivationChange
                and self.isActiveWindow() and user32 is not None):
            # окно активировали (например, кнопкой в панели задач) - наверх
            user32.SetWindowPos(
                int(self.winId()), wintypes.HWND(HWND_TOP), 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
            )

    # ---------- булавка: поверх всех окон ----------
    def set_pinned(self, pinned, apply=True):
        self.pinned = pinned
        self.pin_btn.setChecked(pinned)
        self.pin_btn.setToolTip(
            "Открепить (вернуть на рабочий стол)" if pinned
            else "Закрепить поверх всех окон"
        )
        if apply and user32 is not None:
            after = HWND_TOPMOST if pinned else HWND_NOTOPMOST
            user32.SetWindowPos(
                int(self.winId()), wintypes.HWND(after), 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
            )
        self.save_timer.start()

    # ---------- боковая панель заметок ----------
    def set_notes_open(self, is_open, resize=True):
        if is_open == self.notes_is_open:
            self.notes_btn.setChecked(is_open)
            return
        extra = NOTES_W + NOTES_GAP
        self.notes_is_open = is_open
        self.notes_panel.setVisible(is_open)
        self.grip_main.setVisible(not is_open)
        self.notes_btn.setChecked(is_open)
        self.setMinimumWidth(300 + extra if is_open else 300)
        if resize:
            self.resize(self.width() + (extra if is_open else -extra),
                        self.height())
            if is_open:
                self.fit_to_screen()
        self.save_timer.start()

    def fit_to_screen(self):
        """Если панель заметок вылезла за край экрана, сдвинуть окно влево."""
        scr = self.screen()
        if scr is None:
            return
        geo = scr.availableGeometry()
        overflow = self.x() + self.width() - (geo.x() + geo.width())
        if overflow > 0:
            self.move(max(geo.x(), self.x() - overflow), self.y())

    # ---------- не сворачиваться по Win+D ----------
    def keep_on_desktop(self):
        # после полуночи перерисовать рамку на новой дате
        today = QDate.currentDate()
        if today != self.last_today:
            self.last_today = today
            self.cal.updateCells()
        if user32 is None:
            return
        hwnd = int(self.winId())
        if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        if self.pinned:
            # закреплено: держим поверх всех окон
            user32.SetWindowPos(
                hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
            )
        elif not self.isActiveWindow():
            # пока вы не пишете в окне, держим его под остальными окнами
            user32.SetWindowPos(
                hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
            )

    # ---------- список дел ----------
    def key(self, qdate):
        return qdate.toString(Qt.ISODate)

    def style_item(self, item):
        done = item.checkState() == Qt.Checked
        font = item.font()
        font.setStrikeOut(done)
        item.setFont(font)
        item.setForeground(QColor(MUTED if done else TEXT))

    def make_item(self, text, done):
        item = QListWidgetItem(text)
        item.setFlags(
            Qt.ItemIsEnabled | Qt.ItemIsSelectable
            | Qt.ItemIsUserCheckable | Qt.ItemIsEditable
        )
        item.setCheckState(Qt.Checked if done else Qt.Unchecked)
        self.style_item(item)
        return item

    def show_tasks_for(self, qdate):
        self.current = qdate
        self.list.blockSignals(True)
        self.list.clear()
        for t in self.tasks.get(self.key(qdate), []):
            self.list.addItem(self.make_item(t["text"], t["done"]))
        self.list.blockSignals(False)
        self.update_title()
        self.update_water()

    def update_title(self):
        text = "Дела на " + self.current.toString("dd.MM.yyyy")
        tasks = self.tasks.get(self.key(self.current), [])
        if tasks:
            done = sum(1 for t in tasks if t["done"])
            text += f"  ·  {done}/{len(tasks)}"
        self.title.setText(text)

    def update_water(self):
        n = self.water.get(self.key(self.current), 0)
        self.water_bar.set_count(n)
        if n >= WATER_GLASSES:
            self.water_label.setText(f"{n}/{WATER_GLASSES} ✓")
            self.water_label.setStyleSheet(f"color: {TOMATO};")
        else:
            self.water_label.setText(f"{n}/{WATER_GLASSES}")
            self.water_label.setStyleSheet("")

    def on_water_changed(self, n):
        k = self.key(self.current)
        if n > 0:
            self.water[k] = n
        else:
            self.water.pop(k, None)
        self.update_water()
        self.save_timer.start()

    def on_date_changed(self):
        self.show_tasks_for(self.cal.selectedDate())

    def collect(self):
        """Собрать список дел текущего дня из виджета и сохранить."""
        tasks = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            text = it.text().strip()
            if text:
                tasks.append(
                    {"text": text, "done": it.checkState() == Qt.Checked}
                )
        k = self.key(self.current)
        if tasks:
            self.tasks[k] = tasks
        else:
            self.tasks.pop(k, None)
        self.update_title()
        self.refresh_highlights()
        self.save_timer.start()

    def on_item_changed(self, item):
        self.list.blockSignals(True)
        if not item.text().strip():
            # пустое дело после редактирования удаляем
            self.list.takeItem(self.list.row(item))
        else:
            self.style_item(item)
        self.list.blockSignals(False)
        self.collect()

    def add_task(self):
        text = self.input.text().strip()
        if not text:
            return
        self.list.blockSignals(True)
        self.list.addItem(self.make_item(text, False))
        self.list.blockSignals(False)
        self.input.clear()
        self.collect()

    def delete_selected(self):
        row = self.list.currentRow()
        if row >= 0 and self.list.currentItem() is not None:
            self.list.blockSignals(True)
            self.list.takeItem(row)
            self.list.blockSignals(False)
            self.collect()

    def refresh_highlights(self):
        # сбросить старую подсветку и поставить новую
        self.cal.setDateTextFormat(QDate(), QTextCharFormat())

        open_fmt = QTextCharFormat()      # есть невыполненные дела
        open_fmt.setFontWeight(QFont.Bold)
        open_fmt.setBackground(QColor(NOTE_BG))
        open_fmt.setForeground(QColor(TEXT))

        done_fmt = QTextCharFormat()      # все дела выполнены
        done_fmt.setFontWeight(QFont.Bold)
        done_fmt.setBackground(QColor(DONE_BG))
        done_fmt.setForeground(QColor(NAV_TEXT))

        for k, tasks in self.tasks.items():
            d = QDate.fromString(k, Qt.ISODate)
            if not d.isValid() or not tasks:
                continue
            all_done = all(t["done"] for t in tasks)
            self.cal.setDateTextFormat(d, done_fmt if all_done else open_fmt)

    # ---------- сохранение / загрузка ----------
    def load_data(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}

        if "tasks" in data:
            self.tasks = data["tasks"]
        else:
            # старый формат: одна текстовая заметка на день -> список дел
            self.tasks = {}
            old = data.get("notes", {})
            if old:
                try:
                    shutil.copyfile(DATA_FILE, BACKUP_FILE)  # копия на всякий случай
                except OSError:
                    pass
            for k, text in old.items():
                lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
                if lines:
                    self.tasks[k] = [{"text": ln, "done": False} for ln in lines]

        self.water = {}
        for k, v in data.get("water", {}).items():
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
            if n > 0:
                self.water[k] = n

        self.free_notes.blockSignals(True)
        self.free_notes.setPlainText(data.get("free_notes", ""))
        self.free_notes.blockSignals(False)

        pos = data.get("pos")
        size = data.get("size")
        if size and len(size) == 2:
            self.resize(size[0], size[1])
        if pos and len(pos) == 2:
            self.move(pos[0], pos[1])
        if data.get("notes_open"):
            self.set_notes_open(True, resize=False)
        if data.get("pinned"):
            self.set_pinned(True, apply=False)

    def save_data(self):
        data = {
            "tasks": self.tasks,
            "free_notes": self.free_notes.toPlainText(),
            "water": self.water,
            "notes_open": self.notes_is_open,
            "pinned": self.pinned,
            "pos": [self.x(), self.y()],
            "size": [self.width(), self.height()],
        }
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)  # безопасная замена файла
        except OSError as e:
            print("Не удалось сохранить:", e)

    # ---------- перетаскивание окна ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 44:
            self.drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        if self.drag_offset is not None:
            self.drag_offset = None
            self.save_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.save_timer.start()

    def closeEvent(self, event):
        self.save_data()
        super().closeEvent(event)


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "DeskCalendar.Widget")
        except Exception:
            pass
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    # без цветной каймы вокруг букв на прозрачном окне
    font.setStyleStrategy(QFont.NoSubpixelAntialias)
    app.setFont(font)
    app.setWindowIcon(make_icon())
    save_icon_file()
    w = DeskCalendar()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
