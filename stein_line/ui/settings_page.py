from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
                             QPushButton, QFileDialog, QDoubleSpinBox, QSpinBox, 
                             QGroupBox, QHBoxLayout, QLabel)

class SettingsPage(QWidget):
    def __init__(self, config, on_apply):
        super().__init__()
        self.config = config
        self.on_apply = on_apply
        self.init_ui()

    def init_ui(self):
        # Using a main layout with margins for that "MuseScore" airy feel
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(20)

        header = QLabel("PROJECT SETTINGS")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        self.main_layout.addWidget(header)

        form_group = QGroupBox("Environment Paths")
        form = QFormLayout(form_group)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(15)

        self.name_edit = QLineEdit(self.config.project_name)
        form.addRow("Project Name:", self.name_edit)

        # Source Browse
        self.source_edit = QLineEdit(self.config.source_root)
        src_btn = QPushButton("Browse")
        src_btn.clicked.connect(self._browse_src)
        src_row = QHBoxLayout()
        src_row.addWidget(self.source_edit)
        src_row.addWidget(src_btn)
        form.addRow("Evidence Root:", src_row)

        self.reg_edit = QLineEdit(self.config.registry_db_path)
        form.addRow("Registry DB:", self.reg_edit)

        self.intel_edit = QLineEdit(self.config.intelligence_db_path)
        form.addRow("Intelligence DB:", self.intel_edit)
        
        self.main_layout.addWidget(form_group)

        # Push the button to the bottom
        self.main_layout.addStretch()

        self.apply_btn = QPushButton("Initialize Project Environment")
        self.apply_btn.setObjectName("PrimaryAction")
        self.apply_btn.setFixedHeight(40)
        self.apply_btn.clicked.connect(self._apply)
        self.main_layout.addWidget(self.apply_btn)

    def _browse_src(self):
        path = QFileDialog.getExistingDirectory(self, "Select Root")
        if path: self.source_edit.setText(path)

    def _apply(self):
        self.config.project_name = self.name_edit.text()
        self.config.source_root = self.source_edit.text()
        self.config.registry_db_path = self.reg_edit.text()
        self.config.intelligence_db_path = self.intel_edit.text()
        if self.on_apply: self.on_apply()