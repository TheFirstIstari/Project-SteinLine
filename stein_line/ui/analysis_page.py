from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar, QFrame
from ..core.registry_worker import RegistryWorker
from ..core.analysis_worker import AnalysisWorker

class AnalysisPage(QWidget):
    def __init__(self, config, console):
        super().__init__()
        self.config = config
        self.console = console
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        # Registry Section
        reg_box = QFrame()
        reg_box.setStyleSheet("background-color: #1c2128; border-radius: 4px;")
        reg_layout = QVBoxLayout(reg_box)
        
        self.reg_btn = QPushButton("Start File Fingerprinting")
        self.reg_btn.clicked.connect(self.run_hashing)
        reg_layout.addWidget(self.reg_btn)
        
        self.pbar = QProgressBar()
        reg_layout.addWidget(self.pbar)
        layout.addWidget(reg_box)

        # Reasoner Section
        inf_box = QFrame()
        inf_box.setStyleSheet("background-color: #1c2128; border-radius: 4px;")
        inf_layout = QVBoxLayout(inf_box)
        
        self.inf_btn = QPushButton("Start Neural Reasoner")
        self.inf_btn.clicked.connect(self.run_inference)
        inf_layout.addWidget(self.inf_btn)
        layout.addWidget(inf_box)
        
        layout.addStretch()

    def run_hashing(self):
        if not self.config.is_ready:
            self.console.append_log("ERROR: Project not initialized.")
            return
            
        self.reg_btn.setEnabled(False)
        self.worker = RegistryWorker(self.config)
        self.worker.status_signal.connect(self.console.append_log)
        self.worker.progress_signal.connect(self.pbar.setValue)
        self.worker.finished_signal.connect(lambda: self.reg_btn.setEnabled(True))
        self.worker.start()

    def run_inference(self):
        if not self.config.is_ready:
            self.console.append_log("ERROR: Project not initialized.")
            return

        self.inf_btn.setEnabled(False)
        self.analyzer = AnalysisWorker(self.config)
        self.analyzer.status_signal.connect(self.console.append_log)
        self.analyzer.start()