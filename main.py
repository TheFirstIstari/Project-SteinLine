import sys
import os
from PySide6.QtWidgets import QApplication
from stein_line.ui.main_window import MainWindow
from stein_line.utils.project_config import ProjectConfig

def main():
    app = QApplication(sys.argv)
    
    # Load Styles
    qss_path = os.path.join(os.path.dirname(__file__), "stein_line", "ui", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())

    # Initialize Config
    config = ProjectConfig.load("last_project.json")
    config.auto_tune() # Auto-detect hardware on startup

    # Initialize Window
    window = MainWindow(config)
    window.show()

    # Log the auto-restoration
    if config.source_root:
        window.console.append_log("SESSION_RESTORED: Previous project paths loaded.")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()