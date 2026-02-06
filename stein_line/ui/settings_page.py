from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QFileDialog, QDoubleSpinBox, QSpinBox, 
                             QGroupBox, QHBoxLayout, QLabel)
from PySide6.QtCore import Qt

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

        layout.addStretch()

        self.apply_btn = QPushButton("Initialize Forensic Session")
        self.apply_btn.setObjectName("PrimaryAction")
        self.apply_btn.setFixedHeight(45)
        self.apply_btn.clicked.connect(self._apply)
        layout.addWidget(self.apply_btn)

    def update_ui_fields(self):
        """Update the visible text fields from the internal config object."""
        self.name_edit.setText(self.config.project_name)
        self.source_edit.setText(self.config.source_root)
        self.reg_edit.setText(self.config.registry_db_path)
        self.intel_edit.setText(self.config.intelligence_db_path)
        self.vram_spin.setValue(self.config.vram_allocation)
        self.thread_spin.setValue(self.config.cpu_workers)

    def _select_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Root")
        if path: self.source_edit.setText(path)

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
            self.on_apply("READY")
        else:
            self.on_apply("ERROR: Validation failed.")