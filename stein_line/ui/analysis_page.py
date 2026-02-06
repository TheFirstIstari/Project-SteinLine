from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QProgressBar, QFrame, QHBoxLayout)
from PySide6.QtCore import Qt
from ..core.registry_worker import RegistryWorker

class AnalysisPage(QWidget):
    def __init__(self, config, console):
        super().__init__()
        self.config = config
        self.console = console # Reference to main console
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        header = QLabel("PIPELINE_ORCHESTRATION")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(header)

        # 1. Registry Section
        reg_group = QFrame()
        reg_group.setStyleSheet("background-color: #1c2128; border-radius: 8px;")
        reg_layout = QVBoxLayout(reg_group)
        reg_layout.setContentsMargins(20, 20, 20, 20)

        reg_title = QLabel("Step 1: File Fingerprinting")
        reg_title.setStyleSheet("font-weight: bold; color: #539bf5;")
        reg_layout.addWidget(reg_title)

        self.reg_btn = QPushButton("Scan and Populate Registry")
        self.reg_btn.setObjectName("PrimaryAction")
        self.reg_btn.clicked.connect(self.run_registry)
        reg_layout.addWidget(self.reg_btn)

        self.pbar = QProgressBar()
        self.pbar.setStyleSheet("QProgressBar { height: 10px; }")
        reg_layout.addWidget(self.pbar)

        self.stat_label = QLabel("Ready to index data...")
        self.stat_label.setStyleSheet("font-size: 10px; color: #768390;")
        reg_layout.addWidget(self.stat_label)

        layout.addWidget(reg_group)
        layout.addStretch()

    def run_registry(self):
        self.reg_btn.setEnabled(False)
        self.worker = RegistryWorker(self.config)
        
        # Connect Signals to UI
        self.worker.status_signal.connect(self.console.append_log)
        self.worker.progress_signal.connect(self.pbar.setValue)
        self.worker.stats_signal.connect(lambda cur, tot: self.stat_label.setText(f"Processing: {cur:,} / {tot:,} files"))
        self.worker.finished_signal.connect(self.on_registry_finished)
        
        self.worker.start()

    def on_registry_finished(self, total):
        self.reg_btn.setEnabled(True)
        self.stat_label.setText(f"Indexing Complete. {total:,} new files registered.")