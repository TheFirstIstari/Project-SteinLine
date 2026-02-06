from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QDockWidget, QLabel, QMenuBar, QMenu, QTabWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from .settings_page import SettingsPage
from .analysis_page import AnalysisPage
from .log_console import LogConsole

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("SteinLine Workstation")
        self.resize(1400, 950)

        # 1. Initialize the Console and Menus first
        self.console = LogConsole()
        self.init_menu_bar()

        # 2. Central Widget Placeholder
        self.central_area = QWidget()
        self.central_layout = QVBoxLayout(self.central_area)
        self.board_placeholder = QLabel("FORENSIC_BOARD_WORKSPACE")
        self.board_placeholder.setAlignment(Qt.AlignCenter)
        self.board_placeholder.setStyleSheet("font-size: 24px; color: #2d333b; font-weight: bold;")
        self.central_layout.addWidget(self.board_placeholder)
        self.setCentralWidget(self.central_area)

        # 3. Docking Infrastructure
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # 4. Create Docks
        # Note: we pass self.view_menu (created in init_menu_bar) to add toggles
        self.setup_dock = self.create_dock("Project Setup", SettingsPage(self.config, self.on_config_applied))
        self.analysis_dock = self.create_dock("Analysis Engine", AnalysisPage(self.config, self.console))
        self.console_dock = self.create_dock("System Console", self.console)

        # Initial Layout Placement
        self.addDockWidget(Qt.LeftDockWidgetArea, self.setup_dock)
        self.tabifyDockWidget(self.setup_dock, self.analysis_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.console_dock)

    def init_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        exit_app = QAction("Exit", self)
        exit_app.triggered.connect(self.close)
        file_menu.addAction(exit_app)

        # View Menu - STORE REFERENCE for create_dock to use
        self.view_menu = menubar.addMenu("View")
        
        # Analysis Menu
        analysis_menu = menubar.addMenu("Analysis")
        run_hashing = QAction("Run File Hashing", self)
        analysis_menu.addAction(run_hashing)

    def create_dock(self, title, widget):
        """Standardizes dock creation and adds toggle to View menu."""
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        
        # Add the dock's built-in toggle action to our View menu reference
        self.view_menu.addAction(dock.toggleViewAction())
        return dock

    def on_config_applied(self):
        self.console.append_log(f"Configuration verified: {self.config.project_name}")