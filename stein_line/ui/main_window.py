from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QFrame, QPushButton, QStackedWidget, QLabel, 
                             QButtonGroup, QSplitter)
from PySide6.QtCore import Qt
from .settings_page import SettingsPage
from .log_console import LogConsole

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("SteinLine Workstation")
        self.resize(1200, 850)
        
        # Central Container
        self.root = QWidget()
        self.setCentralWidget(self.root)
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setFixedHeight(45)
        self.init_top_bar()
        self.layout.addWidget(self.top_bar)

        # 2. Workspace Splitter (Content vs Console)
        self.v_splitter = QSplitter(Qt.Vertical)
        
        # Horizontal Splitter (Sidebar vs Content)
        self.h_container = QWidget()
        self.h_layout = QHBoxLayout(self.h_container)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200)
        self.init_sidebar()
        
        # Content
        self.content_stack = QStackedWidget()
        self.settings_page = SettingsPage(self.config, self.on_config_applied)
        self.content_stack.addWidget(self.settings_page)
        
        # Default Page Stubs
        self.content_stack.addWidget(QLabel("ANALYSIS_ENGINE_STUB"))
        self.content_stack.addWidget(QLabel("FORENSIC_BOARD_STUB"))

        self.h_layout.addWidget(self.sidebar)
        self.h_layout.addWidget(self.content_stack)

        # 3. Console Wrapper
        self.console_wrapper = QFrame()
        self.console_wrapper.setObjectName("ConsoleWrapper")
        self.console_layout = QVBoxLayout(self.console_wrapper)
        self.console_layout.setContentsMargins(10, 5, 10, 5)
        self.console = LogConsole()
        self.console_layout.addWidget(self.console)

        # Add to Splitter
        self.v_splitter.addWidget(self.h_container)
        self.v_splitter.addWidget(self.console_wrapper)
        self.v_splitter.setStretchFactor(0, 4)
        self.v_splitter.setStretchFactor(1, 1)

        self.layout.addWidget(self.v_splitter)

    def init_top_bar(self):
        layout = QHBoxLayout(self.top_bar)
        title = QLabel("STEINLINE // NATIVE WORKSTATION")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        layout.addStretch()
        self.status = QLabel("SYSTEM_READY")
        self.status.setStyleSheet("color: #3fb950; font-family: monospace; font-size: 10px;")
        layout.addWidget(self.status)

    def init_sidebar(self):
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        pages = [("Project Setup", 0), ("Analysis Engine", 1), ("Forensic Board", 2)]
        for text, idx in pages:
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCheckable(True)
            if idx == 0: btn.setChecked(True)
            btn.clicked.connect(lambda _, i=idx: self.content_stack.setCurrentIndex(i))
            self.nav_group.addButton(btn)
            layout.addWidget(btn)

    def on_config_applied(self):
        self.console.append_log(f"Session Updated: {self.config.project_name}")
        self.status.setText("CONFIGURATION_SET")