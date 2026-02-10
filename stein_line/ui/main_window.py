from PySide6.QtWidgets import (QMainWindow, QDockWidget, QMenuBar, QMenu, QFileDialog)
from PySide6.QtCore import Qt, Slot, QSettings
from PySide6.QtGui import QAction

from .settings_page import SettingsPage
from .analysis_page import AnalysisPage
from .log_console import LogConsole
from .board_view import BoardView
from .performance_dashboard import PerformanceDashboard

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("SteinLine Forensic Workstation")
        self.resize(1600, 1000)

        # 1. CORE ENGINE & VIEWS
        self.console = LogConsole()
        self.board_view = BoardView(self.config)
        self.setCentralWidget(self.board_view)

        # 2. DOCKING CONFIGURATION (DAW Style)
        self.setDockNestingEnabled(True)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)

        # 3. INITIALIZE MODULAR DOCKS
        self.init_menu_bar()
        self.init_modules()

        # 4. RESTORE PREVIOUS LAYOUT
        self.load_ui_state()

        # Connect Neural Stream
        self.analysis_page.engine_started_signal.connect(self.connect_worker_to_board)
        self.board_view.sig_node_selected.connect(self.console.append_log)

    def init_modules(self):
        """Create and place all independent tool modules."""
        self.settings_page = SettingsPage(self.config, self.on_config_applied)
        self.analysis_page = AnalysisPage(self.config, self.console)
        self.perf_dashboard = PerformanceDashboard(self.config)

        self.setup_dock = self.create_module("PROJECT_SETUP", self.settings_page, Qt.LeftDockWidgetArea)
        self.analysis_dock = self.create_module("ANALYSIS_ENGINE", self.analysis_page, Qt.LeftDockWidgetArea)
        self.perf_dock = self.create_module("PERFORMANCE", self.perf_dashboard, Qt.RightDockWidgetArea)
        self.console_dock = self.create_module("SYSTEM_CONSOLE", self.console, Qt.BottomDockWidgetArea)

        # Initial grouping
        self.tabifyDockWidget(self.setup_dock, self.analysis_dock)

    def create_module(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{title}") # Required for persistence
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock

    def init_menu_bar(self):
        menubar = self.menuBar()
        # File
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Exit").triggered.connect(self.close)
        # View (Modules)
        self.view_menu = menubar.addMenu("Modules")
        # Layouts
        layout_menu = menubar.addMenu("Workspace")
        layout_menu.addAction("Reset Default Layout").triggered.connect(self.reset_layout)

    def connect_worker_to_board(self, worker):
        worker.fact_signal.connect(self.board_view.stream_facts)

    def on_config_applied(self, status):
        self.console.append_log(f"INIT_RESULT: {status}")
        if "READY" in status: self.board_view.load_universe()

    # --- PERSISTENCE LOGIC ---
    def save_ui_state(self):
        settings = QSettings("SteinLineProject", "Workstation")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def load_ui_state(self):
        settings = QSettings("SteinLineProject", "Workstation")
        if settings.value("geometry"):
            self.restoreGeometry(settings.value("geometry"))
        if settings.value("windowState"):
            self.restoreState(settings.value("windowState"))

    def reset_layout(self):
        """Clears saved UI state to return to factory defaults."""
        settings = QSettings("SteinLineProject", "Workstation")
        settings.clear()
        self.console.append_log("UI_RESET: Restart application to apply default layout.")

    def closeEvent(self, event):
        self.save_ui_state()
        super().closeEvent(event)