from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QFileDialog, QFormLayout, QDoubleSpinBox, 
                             QSpinBox, QCheckBox, QLabel, QGroupBox)
from PySide6.QtCore import Qt

class SettingsPage(QWidget):
    """Configuration screen for project paths and hardware limits."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. Path Configuration Group
        path_group = QGroupBox("Project Environment")
        path_form = QFormLayout(path_group)

        self.name_edit = QLineEdit(self.config.project_name)
        path_form.addRow("Investigation Name:", self.name_edit)

        # Source Root Selector
        self.source_edit = QLineEdit(self.config.source_root)
        source_btn = QPushButton("Browse")
        source_btn.clicked.connect(self._select_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit)
        source_row.addWidget(source_btn)
        path_form.addRow("Evidence Root (VOL Folders):", source_row)

        # Registry DB Selector
        self.registry_edit = QLineEdit(self.config.registry_db_path)
        reg_btn = QPushButton("Select File")
        reg_btn.clicked.connect(self._select_registry)
        reg_row = QHBoxLayout()
        reg_row.addWidget(self.registry_edit)
        reg_row.addWidget(reg_btn)
        path_form.addRow("Local Registry DB:", reg_row)

        # Intelligence DB Selector
        self.intel_edit = QLineEdit(self.config.intelligence_db_path)
        intel_btn = QPushButton("Select File")
        intel_btn.clicked.connect(self._select_intel)
        intel_row = QHBoxLayout()
        intel_row.addWidget(self.intel_edit)
        intel_row.addWidget(intel_btn)
        path_form.addRow("Intelligence DB (Pi/Remote):", intel_row)

        layout.addWidget(path_group)

        # 2. Hardware Allocation Group
        hw_group = QGroupBox("Computational Resource Allocation")
        hw_form = QFormLayout(hw_group)

        self.vram_spin = QDoubleSpinBox()
        self.vram_spin.setRange(0.1, 0.9)
        self.vram_spin.setSingleStep(0.05)
        self.vram_spin.setValue(self.config.vram_allocation)
        hw_form.addRow("GPU VRAM Utilization Cap:", self.vram_spin)

        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, 64)
        self.worker_spin.setValue(self.config.cpu_workers)
        hw_form.addRow("Concurrent CPU Workers:", self.worker_spin)

        self.gpu_ocr_check = QCheckBox("Enable GPU OCR (Accelerated)")
        self.gpu_ocr_check.setChecked(self.config.use_gpu_ocr)
        hw_form.addRow(self.gpu_ocr_check)

        layout.addWidget(hw_group)
        layout.addStretch()

        # Save Button
        save_btn = QPushButton("Apply and Initialize Project")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet("background-color: #00ff41; color: black; font-weight: bold;")
        save_btn.clicked.connect(self._apply_settings)
        layout.addWidget(save_btn)

    def _select_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Evidence Root Folder")
        if path: self.source_edit.setText(path)

    def _select_registry(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Registry DB Location", "", "SQLite DB (*.db)")
        if path: self.registry_edit.setText(path)

    def _select_intel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Intelligence DB Location", "", "SQLite DB (*.db)")
        if path: self.intel_edit.setText(path)

    def _apply_settings(self):
        """Update the config object from the UI values."""
        self.config.project_name = self.name_edit.text()
        self.config.source_root = self.source_edit.text()
        self.config.registry_db_path = self.registry_edit.text()
        self.config.intelligence_db_path = self.intel_edit.text()
        self.config.vram_allocation = self.vram_spin.value()
        self.config.cpu_workers = self.worker_spin.value()
        self.config.use_gpu_ocr = self.gpu_ocr_check.isChecked()
        print("Settings Applied.")