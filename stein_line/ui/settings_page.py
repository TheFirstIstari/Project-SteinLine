from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QFileDialog, QDoubleSpinBox, QSpinBox, 
                             QGroupBox, QHBoxLayout, QLabel, QGridLayout)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from pathlib import Path

class SettingsPage(QWidget):
    def __init__(self, config, on_apply_callback):
        super().__init__()
        self.config = config
        self.on_apply = on_apply_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        header = QLabel("PROJECT_ENVIRONMENT_SETTINGS")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(header)

        path_group = QGroupBox("Environment Paths")
        path_form = QFormLayout(path_group)
        path_form.setContentsMargins(20, 20, 20, 20)
        path_form.setSpacing(15)

        self.name_edit = QLineEdit(self.config.project_name)
        path_form.addRow("Project Name:", self.name_edit)

        self.source_edit = QLineEdit(self.config.source_root)
        src_btn = QPushButton("Browse")
        src_btn.clicked.connect(self._select_source)
        source_row = QHBoxLayout(); source_row.addWidget(self.source_edit); source_row.addWidget(src_btn)
        path_form.addRow("Evidence Root:", source_row)

        self.reg_edit = QLineEdit(self.config.registry_db_path)
        path_form.addRow("Registry DB:", self.reg_edit)

        self.intel_edit = QLineEdit(self.config.intelligence_db_path)
        path_form.addRow("Intelligence DB:", self.intel_edit)
        layout.addWidget(path_group)

        perf_group = QGroupBox("Resource Tuning")
        perf_form = QFormLayout(perf_group)
        self.vram_spin = QDoubleSpinBox(); self.vram_spin.setRange(0.1, 0.95); self.vram_spin.setValue(self.config.vram_allocation)
        perf_form.addRow("vLLM VRAM Cap:", self.vram_spin)
        self.thread_spin = QSpinBox(); self.thread_spin.setRange(1, 64); self.thread_spin.setValue(self.config.cpu_workers)
        perf_form.addRow("CPU Workers:", self.thread_spin)
        layout.addWidget(perf_group)

        session_group = QGroupBox("Current Session")
        session_grid = QGridLayout(session_group)
        session_grid.setContentsMargins(20, 16, 20, 16)
        session_grid.setHorizontalSpacing(12)
        session_grid.setVerticalSpacing(8)

        self.session_name = QLabel("-")
        self.session_source = QLabel("-")
        self.session_registry = QLabel("-")
        self.session_intel = QLabel("-")

        for label in [self.session_name, self.session_source, self.session_registry, self.session_intel]:
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.open_source_btn = QPushButton("Open")
        self.open_registry_btn = QPushButton("Open")
        self.open_intel_btn = QPushButton("Open")
        self.open_source_btn.clicked.connect(lambda: self._open_path(self.config.source_root, True))
        self.open_registry_btn.clicked.connect(lambda: self._open_path(self.config.registry_db_path, False))
        self.open_intel_btn.clicked.connect(lambda: self._open_path(self.config.intelligence_db_path, False))

        session_grid.addWidget(QLabel("Project:"), 0, 0)
        session_grid.addWidget(self.session_name, 0, 1, 1, 2)

        session_grid.addWidget(QLabel("Evidence Root:"), 1, 0)
        session_grid.addWidget(self.session_source, 1, 1)
        session_grid.addWidget(self.open_source_btn, 1, 2)

        session_grid.addWidget(QLabel("Registry DB:"), 2, 0)
        session_grid.addWidget(self.session_registry, 2, 1)
        session_grid.addWidget(self.open_registry_btn, 2, 2)

        session_grid.addWidget(QLabel("Intelligence DB:"), 3, 0)
        session_grid.addWidget(self.session_intel, 3, 1)
        session_grid.addWidget(self.open_intel_btn, 3, 2)

        layout.addWidget(session_group)

        layout.addStretch()

        self.apply_btn = QPushButton("Initialize Forensic Session")
        self.apply_btn.setObjectName("PrimaryAction")
        self.apply_btn.setFixedHeight(45)
        self.apply_btn.clicked.connect(self._apply)
        layout.addWidget(self.apply_btn)

        self._refresh_session_card()

    def update_ui_fields(self):
        """Update the visible text fields from the internal config object."""
        self.name_edit.setText(self.config.project_name)
        self.source_edit.setText(self.config.source_root)
        self.reg_edit.setText(self.config.registry_db_path)
        self.intel_edit.setText(self.config.intelligence_db_path)
        self.vram_spin.setValue(self.config.vram_allocation)
        self.thread_spin.setValue(self.config.cpu_workers)
        self._refresh_session_card()

    def _display_path(self, value: str, is_folder: bool) -> str:
        if not value:
            return "-"
        if is_folder:
            return value
        p = Path(value)
        return str(p.parent) if p.parent else str(p)

    def _refresh_session_card(self):
        self.session_name.setText(self.config.project_name or "Unnamed")
        self.session_source.setText(self._display_path(self.config.source_root, True))
        self.session_registry.setText(self._display_path(self.config.registry_db_path, False))
        self.session_intel.setText(self._display_path(self.config.intelligence_db_path, False))

        self.open_source_btn.setEnabled(bool(self.config.source_root))
        self.open_registry_btn.setEnabled(bool(self.config.registry_db_path))
        self.open_intel_btn.setEnabled(bool(self.config.intelligence_db_path))

    def _open_path(self, value: str, is_folder: bool):
        if not value:
            return
        p = Path(value)
        target = p if is_folder else p.parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _select_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Root")
        if path:
            self.source_edit.setText(path)

    def _apply(self):
        self.config.project_name = self.name_edit.text()
        self.config.source_root = self.source_edit.text()
        self.config.registry_db_path = self.reg_edit.text()
        self.config.intelligence_db_path = self.intel_edit.text()
        self.config.vram_allocation = self.vram_spin.value()
        self.config.cpu_workers = self.thread_spin.value()
        
        if self.config.validate():
            # Automatically save as the 'last_project' for next startup
            self.config.save("last_project.json")
            self._refresh_session_card()
            self.on_apply("READY")
        else:
            self._refresh_session_card()
            self.on_apply("ERROR: Validation failed.")