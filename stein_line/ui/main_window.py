from PySide6.QtWidgets import (QMainWindow, QDockWidget, QMenuBar, QMenu, QFileDialog,
                             QToolBar, QLabel, QWidget, QSizePolicy, QMessageBox)
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

        self.init_status_strip()

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
        self.analysis_page.worker_state_signal.connect(self.update_worker_state)
        self.board_view.sig_node_selected.connect(self.console.append_log)

    def init_modules(self):
        """Create and place all independent tool modules."""
        self.settings_page = SettingsPage(self.config, self.on_config_applied)
        self.analysis_page = AnalysisPage(self.config, self.console)
        self.perf_dashboard = PerformanceDashboard(self.config)

        self.analysis_page.set_session_ready(self.config.is_ready)
        self.update_project_status()

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
        layout_menu.addAction("Status Legend").triggered.connect(self.show_status_legend)

    def connect_worker_to_board(self, worker):
        worker.fact_signal.connect(self.board_view.stream_facts)

    def init_status_strip(self):
        self.status_toolbar = QToolBar("Session Status", self)
        self.status_toolbar.setObjectName("SessionStatusStrip")
        self.status_toolbar.setMovable(False)
        self.status_toolbar.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, self.status_toolbar)

        self.project_label = QLabel("")
        self.project_label.setObjectName("StatusProject")
        self.readiness_label = QLabel("")
        self.readiness_label.setObjectName("StatusReadiness")
        self.worker_label = QLabel("WORKER: IDLE")
        self.worker_label.setObjectName("StatusWorker")

        self.status_toolbar.addWidget(self.project_label)
        self.status_toolbar.addSeparator()
        self.status_toolbar.addWidget(self.readiness_label)
        self.status_toolbar.addSeparator()
        self.status_toolbar.addWidget(self.worker_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.status_toolbar.addWidget(spacer)

    def _set_status_badge(self, label: QLabel, status_name: str):
        label.setProperty("status", status_name)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def update_project_status(self):
        self.project_label.setText(f"PROJECT: {self.config.project_name or 'Unnamed'}")
        readiness = "READY" if self.config.is_ready else "NOT_READY"
        self.readiness_label.setText(f"SESSION: {readiness}")
        self._set_status_badge(self.readiness_label, "ready" if self.config.is_ready else "not_ready")

    @Slot(str)
    def update_worker_state(self, state: str):
        self.worker_label.setText(f"WORKER: {state}")
        upper = state.upper()
        if "RUNNING" in upper or "RESUMED" in upper:
            badge_state = "running"
        elif "PAUSED" in upper:
            badge_state = "paused"
        elif "CANCELLING" in upper:
            badge_state = "cancelling"
        elif "REJECTED" in upper or "ERROR" in upper:
            badge_state = "error"
        elif "READY" in upper:
            badge_state = "ready"
        else:
            badge_state = "idle"
        self._set_status_badge(self.worker_label, badge_state)

    def on_config_applied(self, status):
        self.console.append_log(f"INIT_RESULT: {status}")
        ready = "READY" in status
        self.analysis_page.set_session_ready(ready)
        self.update_project_status()
        if ready:
            self.board_view.load_universe()

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

    def apply_default_layout(self):
        self.addDockWidget(Qt.LeftDockWidgetArea, self.setup_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.analysis_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.perf_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

        self.tabifyDockWidget(self.setup_dock, self.analysis_dock)
        self.setup_dock.show()
        self.analysis_dock.show()
        self.perf_dock.show()
        self.console_dock.show()

        self.raise_()
        self.activateWindow()

    def reset_layout(self):
        """Clears saved UI state and reapplies factory layout immediately."""
        settings = QSettings("SteinLineProject", "Workstation")
        settings.clear()
        self.apply_default_layout()
        self.save_ui_state()
        self.console.append_log("UI_RESET: Default workspace layout restored.")

    def show_status_legend(self):
        QMessageBox.information(
            self,
            "Status Legend",
            "Ready/Running (Green): session ready or worker active.\n"
            "Paused/Cancelling/Not Ready (Amber): waiting, paused, or stopping.\n"
            "Error/Rejected (Red): command rejected or worker encountered error.\n"
            "Idle (Default): no active task.",
        )

    def closeEvent(self, event):
        self.save_ui_state()
        super().closeEvent(event)