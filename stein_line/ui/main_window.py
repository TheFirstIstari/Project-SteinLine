from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QDockWidget, QLabel, QMenuBar, QMenu, QTabWidget)
from PySide6.QtCore import Qt, Slot
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
        self.setWindowTitle("SteinLine Workstation")
        self.resize(1500, 950)

        self.console = LogConsole()
        self.board_view = BoardView(self.config)
        
        self.init_menu_bar()
        self.setCentralWidget(self.board_view)

        # Docking Configuration
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)
        self.settings_page = SettingsPage(self.config, self.on_config_applied)
        self.setup_dock = self.create_dock("Project Setup", self.settings_page)

        # Pages
        self.setup_dock = self.create_dock("Project Setup", SettingsPage(self.config, self.on_config_applied))
        self.analysis_page = AnalysisPage(self.config, self.console)
        
        # KEY INTEGRATION: Connect the analysis trigger to the board sync
        self.analysis_page.engine_started_signal.connect(self.connect_worker_to_board)
        
        self.analysis_dock = self.create_dock("Analysis Engine", self.analysis_page)
        self.console_dock = self.create_dock("System Console", self.console)
        self.perf_dock = self.create_dock("Performance", PerformanceDashboard(self.config))

        self.addDockWidget(Qt.RightDockWidgetArea, self.perf_dock)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.setup_dock)
        self.tabifyDockWidget(self.setup_dock, self.analysis_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

    @Slot(object)
    def connect_worker_to_board(self, worker):
        """Pipe the worker's live facts into the Graphics Scene."""
        worker.fact_signal.connect(self.board_view.stream_facts)
        self.console.append_log("LIVE_BOARD_LINK: ESTABLISHED")

    def init_menu_bar(self):
        m = self.menuBar()
        file_menu = m.addMenu("File")
        
        open_action = QAction("Open Project...", self)
        open_action.triggered.connect(self.on_open_project)
        
        save_action = QAction("Save Project As...", self)
        save_action.triggered.connect(self.on_save_project)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        
        file_menu.addActions([open_action, save_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        self.view_menu = m.addMenu("View")

    def on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open SteinLine Project", "", "Project Files (*.json)")
        if path:
            new_config = self.config.load(path)
            # Update the existing config object's values
            for key, value in asdict(new_config).items():
                setattr(self.config, key, value)
            
            self.settings_page.update_ui_fields()
            self.on_config_applied("PROJECT_LOADED")

    def on_save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Project Files (*.json)")
        if path:
            if not path.endswith(".json"): path += ".json"
            self.config.save(path)
            self.console.append_log(f"PROJECT_SAVED: {path}")

    def create_dock(self, title, widget):
        d = QDockWidget(title, self)
        d.setWidget(widget)
        self.view_menu.addAction(d.toggleViewAction())
        return d

    def on_config_applied(self, status):
        self.console.append_log(f"INIT: {status}")