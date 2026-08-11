from __future__ import annotations


TOKENS = {
    "bg_basement": "#F7F8FA",
    "bg_layer": "#FFFFFF",
    "bg_weak": "#F2F3F5",
    "fg_neutral": "#212124",
    "fg_muted": "#686B70",
    "fg_subtle": "#868B94",
    "stroke": "#E5E7EB",
    "brand": "#F25B24",
    "brand_pressed": "#D84B18",
    "brand_weak": "#FFF0E8",
    "positive": "#18864B",
    "positive_weak": "#E8F7EF",
    "warning": "#9A6700",
    "warning_weak": "#FFF5CC",
    "critical": "#C9342C",
    "critical_weak": "#FDECEC",
    "informative": "#1769AA",
    "informative_weak": "#EAF3FB",
}


def application_stylesheet() -> str:
    c = TOKENS
    return f"""
    * {{
        font-family: "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 14px;
        color: {c['fg_neutral']};
    }}
    QMainWindow, QWidget#AppRoot {{ background: {c['stroke']}; }}
    QFrame#TitleBar {{ background: {c['bg_layer']}; border-bottom: 1px solid {c['stroke']}; }}
    QLabel#TitleBarName {{ font-weight: 700; font-size: 14px; }}
    QLabel#TitleBarEvent {{ color: {c['fg_muted']}; border-left: 1px solid {c['stroke']}; padding-left: 10px; }}
    QPushButton#TitleControlButton, QPushButton#TitleCloseButton {{
        min-height: 44px; padding: 0; border: none; border-radius: 0; background: transparent; font-size: 16px;
    }}
    QPushButton#TitleControlButton:hover {{ background: {c['bg_weak']}; }}
    QPushButton#TitleCloseButton:hover {{ background: #D9363E; color: white; }}
    QPushButton#UpdateButton {{ min-height: 30px; padding: 0 12px; color: {c['fg_muted']}; background: {c['bg_weak']}; border: none; }}
    QPushButton#UpdateButton:enabled {{ color: white; background: {c['brand']}; }}
    QPushButton#UpdateButton:enabled:hover {{ background: {c['brand_pressed']}; }}
    QFrame#Sidebar {{ background: {c['bg_layer']}; border-right: 1px solid {c['stroke']}; }}
    QLabel#AppTitle {{ font-size: 18px; font-weight: 700; color: {c['brand']}; padding: 8px; }}
    QLabel#PageTitle {{ font-size: 26px; font-weight: 700; }}
    QLabel#PageDescription, QLabel#Muted {{ color: {c['fg_muted']}; }}
    QLabel#SectionTitle {{ font-size: 18px; font-weight: 700; }}
    QLabel#InfoGuide {{
        color: {c['informative']}; background: {c['informative_weak']};
        border: 1px solid #C9DFF2; border-radius: 8px; padding: 10px 12px;
    }}
    QPushButton {{
        min-height: 40px; padding: 0 16px; border: 1px solid {c['stroke']};
        border-radius: 8px; background: {c['bg_layer']}; font-weight: 600;
    }}
    QPushButton:hover {{ background: {c['bg_weak']}; }}
    QPushButton:pressed {{ background: #E9EAEC; }}
    QPushButton:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {{
        border: 2px solid {c['brand']};
    }}
    QPushButton[primary="true"] {{ background: {c['brand']}; color: white; border: none; }}
    QPushButton[primary="true"]:hover {{ background: {c['brand_pressed']}; }}
    QPushButton[danger="true"] {{ color: {c['critical']}; border-color: #F2BBB7; }}
    QPushButton[nav="true"] {{
        min-height: 44px; text-align: left; border: none; border-radius: 8px;
        padding-left: 16px; color: {c['fg_muted']};
    }}
    QPushButton[nav="true"]:checked {{ background: {c['brand_weak']}; color: {c['brand']}; font-weight: 700; }}
    QPushButton[nav="true"]:disabled {{ color: #B1B5BC; background: transparent; }}
    QFrame#Card {{ background: {c['bg_layer']}; border: 1px solid {c['stroke']}; border-radius: 12px; }}
    QFrame#EventCard {{ background: {c['bg_layer']}; border: 1px solid {c['stroke']}; border-radius: 12px; }}
    QLabel#EventCardTitle {{ font-size: 16px; font-weight: 700; }}
    QScrollArea#EventListArea {{ border: none; background: transparent; }}
    QScrollArea#EventListArea > QWidget > QWidget {{ background: transparent; }}
    QLabel#EmptyState {{ color: {c['fg_muted']}; background: {c['bg_layer']}; border: 1px dashed {c['stroke']}; border-radius: 12px; }}
    QLabel#KpiValue {{ font-size: 24px; font-weight: 700; }}
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {{
        min-height: 40px; background: {c['bg_layer']}; border: 1px solid {c['stroke']};
        border-radius: 8px; padding: 0 10px; selection-background-color: {c['brand']};
    }}
    QTextEdit {{ padding: 8px; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QDateEdit[directCalendar="true"] {{ padding-right: 10px; }}
    QDateEdit[directCalendar="true"]::drop-down {{ width: 0px; border: none; background: transparent; }}
    QDateEdit[directCalendar="true"]::down-arrow {{ image: none; width: 0px; height: 0px; }}
    QComboBox QAbstractItemView {{
        background: {c['bg_layer']}; color: {c['fg_neutral']}; border: 1px solid {c['stroke']};
        selection-background-color: {c['brand_weak']}; selection-color: {c['fg_neutral']};
    }}
    QTableWidget, QTreeWidget, QListWidget, QCalendarWidget {{
        background: {c['bg_layer']}; border: 1px solid {c['stroke']}; border-radius: 10px;
        gridline-color: {c['stroke']}; selection-background-color: {c['brand_weak']};
        selection-color: {c['fg_neutral']}; outline: none;
    }}
    QTableWidget {{ alternate-background-color: #FAFAFB; }}
    QListWidget {{ alternate-background-color: #FAFAFB; }}
    QListWidget#UrgentList {{ background: transparent; border: none; }}
    QListWidget#UrgentList::item {{ border: 1px solid {c['stroke']}; border-radius: 8px; padding: 0 14px; }}
    QListWidget#UrgentList::item:selected {{ border: 1px solid {c['brand']}; color: {c['fg_neutral']}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {c['bg_weak']}; }}
    QCalendarWidget QToolButton {{
        background: transparent; color: {c['fg_neutral']}; border: none; font-weight: 700;
    }}
    QCalendarWidget QAbstractItemView:enabled {{
        background: {c['bg_layer']}; color: {c['fg_neutral']};
        selection-background-color: {c['brand_weak']}; selection-color: {c['fg_neutral']};
        alternate-background-color: {c['bg_layer']};
    }}
    QHeaderView {{ background: {c['bg_weak']}; }}
    QHeaderView::section {{
        background: {c['bg_weak']}; color: {c['fg_muted']}; border: none;
        border-bottom: 1px solid {c['stroke']}; padding: 10px; font-weight: 700;
    }}
    QTableCornerButton::section {{ background: {c['bg_weak']}; border: none; border-bottom: 1px solid {c['stroke']}; }}
    QTableWidget::item {{ padding: 7px; }}
    QProgressBar {{ min-height: 14px; border: none; border-radius: 7px; background: {c['bg_weak']}; text-align: center; }}
    QProgressBar::chunk {{ background: {c['brand']}; border-radius: 7px; }}
    QScrollBar:vertical {{
        background: {c['bg_weak']}; width: 12px; margin: 2px; border: none; border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: #C9CDD3; min-height: 32px; border-radius: 4px; margin: 1px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #AEB4BC; }}
    QScrollBar:horizontal {{
        background: {c['bg_weak']}; height: 12px; margin: 2px; border: none; border-radius: 6px;
    }}
    QScrollBar::handle:horizontal {{
        background: #C9CDD3; min-width: 32px; border-radius: 4px; margin: 1px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #AEB4BC; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: transparent; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QTabWidget::pane {{
        background: {c['bg_layer']}; border: 1px solid {c['stroke']}; border-radius: 10px;
        top: -1px;
    }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: {c['bg_weak']}; color: {c['fg_muted']}; border: 1px solid {c['stroke']};
        padding: 11px 24px; min-width: 88px; margin-right: 4px;
        border-top-left-radius: 8px; border-top-right-radius: 8px;
    }}
    QTabBar::tab:selected {{ background: {c['bg_layer']}; color: {c['brand']}; border-bottom-color: {c['bg_layer']}; font-weight: 700; }}
    QTabBar::tab:hover:!selected {{ background: {c['brand_weak']}; color: {c['brand']}; }}
    QSplitter::handle {{ background: {c['bg_weak']}; border-radius: 3px; }}
    QSplitter::handle:hover {{ background: #DDE0E4; }}
    QFrame#CalendarSide {{ background: {c['bg_weak']}; border: 1px solid {c['stroke']}; border-radius: 12px; }}
    QListWidget#CalendarTaskList {{ background: transparent; border: none; }}
    QListWidget#CalendarTaskList::item {{ background: transparent; border: none; }}
    QListWidget#CalendarTaskList::item:selected {{ background: transparent; color: {c['fg_neutral']}; }}
    QFrame#CalendarTaskCard {{ background: {c['bg_layer']}; border: 1px solid {c['stroke']}; border-radius: 10px; }}
    QLabel#CalendarEventName {{ color: {c['fg_muted']}; font-size: 12px; }}
    QLabel#CalendarTaskName {{ color: {c['fg_neutral']}; font-size: 15px; font-weight: 700; }}
    QLabel#StatusBadge {{ border-radius: 9px; padding: 3px 8px; font-size: 12px; font-weight: 700; }}
    QDialog {{ background: {c['bg_basement']}; }}
    QDialogButtonBox QPushButton {{ min-width: 96px; }}
    QToolTip {{ background: {c['fg_neutral']}; color: white; padding: 6px; border: none; }}
    """


def status_color(status: str) -> tuple[str, str]:
    return {
        "완료": (TOKENS["positive"], TOKENS["positive_weak"]),
        "진행중": (TOKENS["informative"], TOKENS["informative_weak"]),
        "확인요청": (TOKENS["warning"], TOKENS["warning_weak"]),
        "보류": (TOKENS["fg_muted"], TOKENS["bg_weak"]),
        "해당없음": (TOKENS["fg_subtle"], TOKENS["bg_weak"]),
        "미착수": (TOKENS["fg_muted"], TOKENS["bg_weak"]),
    }.get(status, (TOKENS["fg_neutral"], TOKENS["bg_layer"]))
