"""Modern Dark Theme Stylesheet for BOLT Desktop Interface."""

DARK_THEME_QSS = """
/* Global Application Styles */
QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0d1117;
    width: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #30363d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #58a6ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0d1117;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #30363d;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #58a6ff;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Sidebar */
QFrame#sidebar {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}

/* Conversation List */
QListWidget#conv_list {
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}

QListWidget#conv_list::item {
    background-color: transparent;
    color: #c9d1d9;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 4px;
}

QListWidget#conv_list::item:hover {
    background-color: #21262d;
    color: #58a6ff;
}

QListWidget#conv_list::item:selected {
    background-color: #1f2937;
    color: #58a6ff;
    border-left: 3px solid #58a6ff;
}

/* Header */
QFrame#header_bar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 6px 16px;
}

/* Buttons */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* Accent Buttons (Send / Primary) */
QPushButton#primary_btn {
    background-color: #1f6feb;
    color: #ffffff;
    border: 1px solid #388bfd;
    font-weight: 600;
}

QPushButton#primary_btn:hover {
    background-color: #388bfd;
    border-color: #58a6ff;
}

QPushButton#primary_btn:pressed {
    background-color: #1158c7;
}

/* Sidebar New Chat Button */
QPushButton#new_chat_btn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-weight: 600;
    padding: 10px 14px;
    border-radius: 6px;
}

QPushButton#new_chat_btn:hover {
    background-color: #2ea043;
}

QPushButton#new_chat_btn:pressed {
    background-color: #196c2e;
}

/* Status Area */
QFrame#status_bar {
    background-color: #161b22;
    border-top: 1px solid #30363d;
    padding: 4px 12px;
}

/* Input Area */
QFrame#input_container {
    background-color: #161b22;
    border-top: 1px solid #30363d;
    padding: 12px 16px;
}

QTextEdit#chat_input {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
}

QTextEdit#chat_input:focus {
    border: 1px solid #58a6ff;
}

/* Dialogs */
QDialog {
    background-color: #161b22;
    color: #e6edf3;
}

QLineEdit, QComboBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 10px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #58a6ff;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* Status Indicator Dot */
QLabel#status_dot_ready {
    color: #3fb950;
    font-size: 14px;
}

QLabel#status_dot_busy {
    color: #d29922;
    font-size: 14px;
}

QLabel#status_dot_error {
    color: #f85149;
    font-size: 14px;
}
"""

