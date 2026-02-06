from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QFileDialog, QDoubleSpinBox, QSpinBox, 
                             QGroupBox, QHBoxLayout, QLabel)

class SettingsPage(QWidget):
    def __init__(self, config, on_apply_callback):
        super().__init__()
        self.config = config
        self.on_apply = on_apply_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        # 1. PATHS
        path_group = QGroupBox("ENVIRONMENT_PATHS")
        path_form = QFormLayout(path_group)
        
        self.source_edit = QLineEdit(self.config.source_root)
        source_btn = QPushButton("Browse")
        source_btn.clicked.connect(self._select_source)
        
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_edit)
        source_row.addWidget(source_btn)
        path_form.addRow("Evidence Root:", source_row)
        
        self.reg_edit = QLineEdit(self.config.registry_db_path)
        path_form.addRow("Registry DB:", self.reg_edit)
        
        self.intel_edit = QLineEdit(self.config.intelligence_db_path)
        path_form.addRow("Intelligence DB:", self.intel_edit)
        layout.addWidget(path_group)

        # 2. HARDWARE CONTROLS (The missing part)
        hw_group = QGroupBox("HARDWARE_RESOURCE_CONTROL")
        hw_form = QFormLayout(hw_group)

        self.vram_ctrl = QDoubleSpinBox()
        self.vram_ctrl.setRange(0.1, 0.95)
        self.vram_ctrl.setSingleStep(0.05)
        self.vram_ctrl.setValue(self.config.vram_allocation)
        hw_form.addRow("GPU VRAM Limit:", self.vram_ctrl)

        self.thread_ctrl = QSpinBox()
        self.thread_ctrl.setRange(1, 64)
        self.thread_ctrl.setValue(self.config.cpu_workers)
        hw_form.addRow("CPU Worker Threads:", self.thread_ctrl)

        layout.addWidget(hw_group)
        layout.addStretch()

        # 3. APPLY
        self.apply_btn = QPushButton("Initialize Project Environment")
        self.apply_btn.setObjectName("PrimaryAction")
        self.apply_btn.setFixedHeight(45)
        self.apply_btn.clicked.connect(self._apply)
        layout.addWidget(self.apply_btn)

    def _select_source(self):
        p = QFileDialog.getExistingDirectory(self, "Select Source")
        if p: self.source_edit.setText(p)

    def _apply(self):
        # Write UI values back to the config object
        self.config.source_root = self.source_edit.text()
        self.config.registry_db_path = self.reg_edit.text()
        self.config.intelligence_db_path = self.intel_edit.text()
        self.config.vram_allocation = self.vram_ctrl.value()
        self.config.cpu_workers = self.thread_ctrl.value()
        
        if self.config.validate():
            self.on_apply("READY")
        else:
            self.on_apply("ERROR: Invalid Paths")