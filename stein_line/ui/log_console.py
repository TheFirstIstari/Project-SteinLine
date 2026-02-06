from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Slot, Qt

class LogConsole(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("SYSTEM_CONSOLE")
        self.header.setStyleSheet("color: #30363d; font-weight: bold; font-size: 10px;")
        
        self.text_area = QPlainTextEdit()
        self.text_area.setObjectName("Console")
        self.text_area.setReadOnly(True)
        self.text_area.setMaximumHeight(200)
        
        layout.addWidget(self.header)
        layout.addWidget(self.text_area)

    @Slot(str)
    def append_log(self, message):
        self.text_area.appendPlainText(f"> {message}")
        # Auto-scroll to bottom
        self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())