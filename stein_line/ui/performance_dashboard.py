from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
                             QSpinBox, QGroupBox, QLabel, QProgressBar)
from PySide6.QtCore import QTimer, Qt
import psutil

class PerformanceDashboard(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.init_ui()
        
        # Timer for live telemetry updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1000) # Update every 1s

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)

        # 1. LIVE MONITORING
        mon_group = QGroupBox("SYSTEM_TELEMETRY")
        mon_layout = QFormLayout(mon_group)
        
        self.ram_bar = QProgressBar()
        self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #388bfd; }")
        mon_layout.addRow("System RAM Usage:", self.ram_bar)
        
        self.vram_label = QLabel("GPU_VRAM: Detecting...")
        mon_layout.addRow("Inference VRAM:", self.vram_label)
        
        layout.addWidget(mon_group)

        # 2. RESOURCE LIMITS (TUNABLES)
        limit_group = QGroupBox("HARDWARE_CAPS")
        form = QFormLayout(limit_group)

        self.ram_spin = QDoubleSpinBox()
        self.ram_spin.setRange(2.0, 512.0)
        self.ram_spin.setValue(self.config.ram_limit_gb)
        self.ram_spin.valueChanged.connect(self._sync_config)
        form.addRow("Max RAM Usage (GB):", self.ram_spin)

        self.vram_spin = QDoubleSpinBox()
        self.vram_spin.setRange(0.1, 0.95)
        self.vram_spin.setValue(self.config.vram_allocation)
        self.vram_spin.valueChanged.connect(self._sync_config)
        form.addRow("vLLM VRAM Limit (%):", self.vram_spin)

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 64)
        self.thread_spin.setValue(self.config.cpu_workers)
        self.thread_spin.valueChanged.connect(self._sync_config)
        form.addRow("Worker Threads:", self.thread_spin)

        layout.addWidget(limit_group)
        layout.addStretch()

    def _update_telemetry(self):
        mem = psutil.virtual_memory()
        self.ram_bar.setValue(int(mem.percent))
        
        # Check if we are over the limit
        current_gb = mem.used / (1024**3)
        if current_gb > self.config.ram_limit_gb:
            self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #f85149; }")
        else:
            self.ram_bar.setStyleSheet("QProgressBar::chunk { background-color: #388bfd; }")

    def _sync_config(self):
        self.config.ram_limit_gb = self.ram_spin.value()
        self.config.vram_allocation = self.vram_spin.value()
        self.config.cpu_workers = self.thread_spin.value()